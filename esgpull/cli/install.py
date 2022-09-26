from __future__ import annotations
from typing import Optional

import rich
import click

from esgpull import Esgpull, Context
from esgpull.types import File
from esgpull.utils import naturalsize
from esgpull.cli.utils import load_facets
from esgpull.cli.decorators import args, opts


@click.command()
@opts.distrib
@opts.dry_run
@opts.date
@opts.force
@opts.since
@opts.latest
@opts.data_node
@opts.replica
@opts.selection_file
@args.facets
def install(
    facets: list[str],
    date: bool,
    data_node: bool,
    distrib: bool,
    dry_run: bool,
    force: bool,
    latest: Optional[bool],
    replica: Optional[bool],
    selection_file: Optional[str],
    since: Optional[str],
) -> None:
    esg = Esgpull()
    ctx = Context(distrib=distrib, latest=latest, since=since, replica=replica)
    load_facets(ctx.query, facets, selection_file)
    hits = ctx.file_hits
    nb_files = sum(hits)
    if dry_run:
        queries = ctx._build_queries_search(
            hits, file=True, max_results=nb_files, offset=0
        )
        rich.print(queries)
    else:
        click.echo(f"Found {nb_files} files.")
        if not force and nb_files > 5000:
            nb_req = nb_files // 50
            message = f"{nb_req} requests will be send to ESGF. Continue?"
            click.confirm(message, default=True, abort=True)
        results = ctx.search(file=True, max_results=nb_files, offset=0)
        files = [File.from_dict(result) for result in results]
        total_size = sum([file.size for file in files])
        click.echo(f"Total size: {naturalsize(total_size)}")
        if not force:
            click.confirm("Continue?", default=True, abort=True)
        installed = esg.install(*files)
        click.echo(f"Installed {len(installed)} new files.")