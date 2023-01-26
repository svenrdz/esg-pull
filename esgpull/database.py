from __future__ import annotations

from contextlib import contextmanager
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import Iterator, Sequence, TypeVar

import alembic.command
import sqlalchemy as sa
import sqlalchemy.orm
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.orm import Session, joinedload, make_transient

from esgpull import __file__
from esgpull.config import Config
from esgpull.models import Table, sql
from esgpull.version import __version__

# from esgpull.exceptions import NoClauseError
# from esgpull.models import Query

T = TypeVar("T")


@dataclass
class Database:
    """
    Main class to interact with esgpull's sqlite db.
    """

    url: str
    run_migrations: InitVar[bool] = True
    _engine: sa.Engine = field(init=False)
    session: Session = field(init=False)
    version: str | None = field(init=False, default=None)

    @staticmethod
    def from_config(config: Config, run_migrations: bool = True) -> Database:
        url = f"sqlite:///{config.paths.db / config.db.filename}"
        return Database(url, run_migrations=run_migrations)

    def __post_init__(self, run_migrations: bool) -> None:
        self._engine = sa.create_engine(self.url)
        self.session = Session(self._engine)
        if run_migrations:
            self._update()

    def _update(self) -> None:
        config = AlembicConfig()
        migrations_path = Path(__file__).parent / "migrations"
        config.set_main_option("script_location", str(migrations_path))
        config.attributes["connection"] = self._engine
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()
        with self._engine.begin() as conn:
            opts = {"version_table": "version"}
            ctx = MigrationContext.configure(conn, opts=opts)
            self.version = ctx.get_current_revision()
        if self.version != head:
            alembic.command.upgrade(config, __version__)
            self.version = head
        if self.version != __version__:
            alembic.command.revision(
                config,
                message="update tables",
                autogenerate=True,
                rev_id=__version__,
            )
            self.version = __version__

    @property
    @contextmanager
    def safe(self) -> Iterator[None]:
        try:
            yield
        except (sa.exc.SQLAlchemyError, KeyboardInterrupt):
            self.session.rollback()
            raise

    def get(
        self,
        table: type[Table],
        sha: str,
        lazy: bool = True,
        detached: bool = False,
    ) -> Table | None:
        if lazy:
            result = self.session.get(table, sha)
        else:
            stmt = sa.select(table).filter_by(sha=sha)
            match self.scalars(stmt.options(joinedload("*")), unique=True):
                case [result]:
                    ...
                case []:
                    result = None
                case [*many]:
                    raise ValueError(f"{len(many)} found, expected 1.")
        if detached and result is not None:
            result = table(**result.asdict())
        return result

    def scalars(
        self, statement: sa.Select[tuple[T]], unique: bool = False
    ) -> Sequence[T]:
        with self.safe:
            result = self.session.scalars(statement)
            if unique:
                result = result.unique()
            return result.all()

    SomeTuple = TypeVar("SomeTuple", bound=tuple)

    def rows(self, statement: sa.Select[SomeTuple]) -> list[sa.Row[SomeTuple]]:
        with self.safe:
            return list(self.session.execute(statement).all())

    def add(self, *items: Table) -> None:
        with self.safe:
            self.session.add_all(items)
            self.session.commit()
            for item in items:
                self.session.refresh(item)

    def delete(self, *items: Table) -> None:
        with self.safe:
            for item in items:
                self.session.delete(item)
            self.session.commit()
        for item in items:
            make_transient(item)

    def __contains__(self, item: Table) -> bool:
        return self.scalars(sql.count(item))[0] > 0

    def merge(self, item: Table, commit: bool = False) -> Table:
        with self.safe:
            result = self.session.merge(item)
            if commit:
                self.session.commit()
        return result

    # def has(
    #     self,
    #     /,
    #     file: File | None = None,
    #     filepath: Path | None = None,
    # ) -> bool:
    #     if file is not None:
    #         clause = File.file_id == file.file_id
    #     elif filepath is not None:
    #         local_path = str(filepath.parent)
    #         filename = filepath.name
    #         local_path_clause = File.local_path == local_path
    #         filename_clause = File.filename == filename
    #         clause = local_path_clause & filename_clause
    #     else:
    #         raise ValueError("TODO: custom error")
    #     with self.select(File) as sel:
    #         matching = sel.where(clause).scalars
    #     return any(matching)

    # def search(
    #     self,
    #     query: Query | None = None,
    #     statuses: Sequence[FileStatus] | None = None,
    #     ids: Sequence[int] | None = None,
    # ) -> list[File]:
    #     clauses: list[sa.ColumnElement] = []
    #     if not statuses and not query and not ids:
    #         raise ValueError("TODO: custom error")
    #     if statuses:
    #         clauses.append(File.status.in_(statuses))
    #     if query:
    #         query_clauses = []
    #         for flat in query.flatten():
    #             flat_clauses = []
    #             for facet in flat:
    #                 # values are in a list, to keep support for CMIP5
    #                 # search by first value only is supported for now
    #                 facet_clause = sa.func.json_extract(
    #                     File.raw, f"$.{facet.name}[0]"
    #                 ).in_(list(facet.values))
    #                 flat_clauses.append(facet_clause)
    #             if flat_clauses:
    #                 query_clauses.append(sa.and_(*flat_clauses))
    #         if query_clauses:
    #             clauses.append(sa.or_(*query_clauses))
    #     if ids:
    #         clauses.append(File.id.in_(ids))
    #     if not clauses:
    #         raise NoClauseError()
    #     with self.select(File) as sel:
    #         return sel.where(sa.and_(*clauses)).scalars

    # def get_deprecated_files(self) -> list[File]:
    #     with (self.select(File) as query, self.select(File) as subquery):
    #         subquery.group_by(File.master_id)
    #         subquery.having(sa.func.count("*") > 1).alias()
    #         join_clause = File.master_id == subquery.stmt.c.master_id
    #         duplicates = query.join(subquery.stmt, join_clause).scalars
    #     duplicates_dict: dict[str, list[File]] = {}
    #     for file in duplicates:
    #         duplicates_dict.setdefault(file.master_id, [])
    #         duplicates_dict[file.master_id].append(file)
    #     deprecated: list[File] = []
    #     for files in duplicates_dict.values():
    #         versions = [int(f.version[1:]) for f in files]
    #         latest_version = "v" + str(max(versions))
    #         for file in files:
    #             if file.version != latest_version:
    #                 deprecated.append(file)
    #     return deprecated