from collections import Counter
from typing import cast

import click
import rich
from click.exceptions import Exit
from sqlalchemy.orm.attributes import InstrumentedAttribute

from esgpull import Esgpull
from esgpull.cli.decorators import opts
from esgpull.db.models import File, FileStatus
from esgpull.utils import format_size


@click.command()
@opts.all
def status(all_: bool):
    esg = Esgpull()
    statuses = set(FileStatus)
    if not all_:
        statuses.remove(FileStatus.done)
    status_attr = cast(InstrumentedAttribute, File.status)
    with esg.db.select(File) as stmt:
        files = stmt.where(status_attr.in_(list(statuses))).scalars
    counts = Counter(file.status for file in files)
    sizes = {
        status: sum(file.size for file in files if file.status == status)
        for status in counts.keys()
    }
    if not counts:
        rich.print("Queue is empty.")
        raise Exit(0)
    table = rich.table.Table(box=rich.box.MINIMAL)
    table.add_column("status", justify="right", style="bold blue")
    table.add_column("#")
    table.add_column("size")
    for status in counts.keys():
        table.add_row(
            status.name, str(counts[status]), format_size(sizes[status])
        )
    rich.print(table)
