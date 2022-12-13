from __future__ import annotations

import atexit
import logging
from contextlib import contextmanager
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any

import click.exceptions
from attrs import define, field
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.logging import RichHandler
from rich.progress import Progress, ProgressColumn
from rich.status import Status
from rich.text import Text

from esgpull.config import Config

logger = logging.getLogger("esgpull")
logging.root.setLevel(logging.DEBUG)
logging.root.addHandler(logging.NullHandler())

# sqlalchemy is very verbose
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

_console = Console(highlight=True)
_err_console = Console(stderr=True)


class Verbosity(IntEnum):
    Normal = 0
    Errors = 1
    Detail = 2
    Debug = 3

    def get_level(self) -> int:
        return [logging.WARNING, logging.WARNING, logging.INFO, logging.DEBUG][
            self
        ]

    def render(self) -> Text:
        return Text(self.name.upper(), style=f"logging.level.{self.name}")


class DummyLive:
    def __enter__(self):
        ...

    def __exit__(self, *args):
        ...


@define
class UI:
    path: Path = field(converter=Path)
    verbosity: Verbosity = Verbosity.Normal
    # max_size: int = 1 << 30

    @staticmethod
    def from_config(
        config: Config, verbosity: Verbosity = Verbosity.Normal
    ) -> UI:
        return UI(config.paths.log, verbosity)

    @contextmanager
    def logging(
        self,
        modulename: str,
        onraise: type[Exception] | None = None,
    ):
        handler: logging.Handler
        temp_path: Path | None = None
        fmt = "[%(asctime)s]  %(levelname)-10s%(name)s\n%(message)s\n"
        datefmt = "%Y-%m-%d %H:%M:%S"
        file_datefmt = "%Y-%m-%d_%H-%M-%S"
        if self.verbosity >= Verbosity.Errors:
            if _err_console.is_terminal or _err_console.is_jupyter:
                handler = RichHandler(
                    console=_err_console,
                    show_path=False,
                    markup=True,
                )
                fmt = "[yellow]· %(name)s ·[/]\n%(message)s"
                datefmt = "[%X]"
            else:
                handler = logging.StreamHandler()
            handler.setLevel(self.verbosity.get_level())
        else:
            date = datetime.utcnow().strftime(file_datefmt)
            filename = "-".join(["esgpull", modulename, date]) + ".log"
            temp_path = self.path / filename
            handler = logging.FileHandler(temp_path)
            handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
        logging.root.addHandler(handler)
        try:
            yield
        except (click.exceptions.Exit, click.exceptions.Abort):
            if temp_path is not None:
                atexit.register(temp_path.unlink)
        except click.exceptions.ClickException:
            raise
        except BaseException as exc:
            tb = exc.__traceback__
            while True:
                if tb is None:
                    break
                elif tb.tb_next is None:
                    break
                tb = tb.tb_next
            if tb is None:
                f_locals = {}
            else:
                f_locals = tb.tb_frame.f_locals
            locals_text = self.render(f_locals, highlight=False)
            logging.root.debug(f"Locals:\n{locals_text}")
            logging.root.exception("Error:")
            if self.verbosity < Verbosity.Errors:
                self.print(
                    f"See [yellow]{temp_path}[/] for error log.",
                    err=True,
                    style="red",
                )
            if onraise is not None:
                raise onraise
            else:
                raise
        else:
            if temp_path is not None:
                atexit.register(temp_path.unlink)
        finally:
            logging.root.removeHandler(handler)

    def print(
        self,
        msg: Any,
        err: bool = False,
        verbosity: Verbosity = Verbosity.Normal,
        **kwargs: Any,
    ) -> None:
        if self.verbosity >= verbosity:
            console = _err_console if err else _console
            if not console.is_interactive:
                kwargs.setdefault("crop", False)
                kwargs.setdefault("overflow", "ignore")
            console.print(msg, **kwargs)

    def render(self, msg: Any, **kwargs: Any) -> str:
        with _console.capture() as capture:
            _console.print(msg, **kwargs)
        return capture.get()

    def live(
        self,
        first: RenderableType,
        *rest: RenderableType,
        disable: bool = False,
    ) -> Live | DummyLive:
        if disable:
            return DummyLive()
        if not rest:
            renderables = first
        else:
            renderables = Group(first, *rest)
        return Live(renderables, console=_console)

    def make_progress(
        self, *columns: str | ProgressColumn, **kwargs: Any
    ) -> Progress:
        return Progress(
            *columns,
            console=_console,
            **kwargs,
        )

    def spinner(self, msg: str) -> Status:
        return _console.status(msg, spinner="earth")