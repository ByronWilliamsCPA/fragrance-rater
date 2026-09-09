"""Command-line interface for Fragrance Rater.

Provides commands for common operations and demonstrates Click best practices
with structured logging integration.
"""

import asyncio
import sys
from collections.abc import Coroutine
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import click
from structlog.stdlib import BoundLogger

from fragrance_rater.core.config import settings
from fragrance_rater.core.database import async_session_maker
from fragrance_rater.services.kaggle_importer import KaggleImporter
from fragrance_rater.services.parfumo_scraper import ParfumoScraper
from fragrance_rater.services.reviewer_service import ReviewerService
from fragrance_rater.utils.logging import get_logger

logger: BoundLogger = get_logger(__name__)


@dataclass
class CLIContext:
    """Typed context object for Click commands.

    Attributes:
        debug (bool): Whether debug logging was requested via ``--debug``.
    """

    debug: bool = False


def mask_database_url(url: str) -> str:
    """Mask any credential in a database URL before it reaches CLI output.

    #CRITICAL: security: a database URL commonly embeds a password in its
    netloc (``scheme://user:password@host/db``). A previous implementation
    truncated the URL with a fixed-offset string slice (``url[:50]``), which
    only hid the password when it happened to land past that offset - for
    short hosts/usernames the password was printed in full.
    #VERIFY: this parses the URL structurally (``urlsplit``) and always
    replaces the password component when one is present, regardless of URL
    length, host length, or username length, then reassembles the URL
    without truncating anything else. Covered by
    ``tests/unit/test_cli.py::test_mask_database_url*``.

    Args:
        url (str): Raw database URL, potentially containing credentials.

    Returns:
        str: The URL with any password replaced by ``***``. URLs with no
            embedded password (e.g. local SQLite paths, or connection
            strings with no user info) are returned unchanged.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        # Not a well-formed URL (e.g. a bare SQLite file path) - nothing to
        # mask, and nothing unmasked to leak either.
        return url

    if parts.password is None:
        return url

    userinfo = parts.username or ""
    masked_netloc = f"{userinfo}:***@{parts.hostname or ''}"
    if parts.port is not None:
        masked_netloc += f":{parts.port}"

    return urlunsplit(
        (parts.scheme, masked_netloc, parts.path, parts.query, parts.fragment)
    )


def run_async[T](coro: Coroutine[object, object, T]) -> T:
    """Run an async coroutine to completion in a fresh event loop.

    Args:
        coro (Coroutine[object, object, T]): The coroutine to execute.

    Returns:
        T: The coroutine's return value.
    """
    return asyncio.run(coro)


@click.group()
@click.version_option(version="0.1.0", prog_name="fragrance-rater")
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """Fragrance Rater - Personal fragrance evaluation and recommendation system."""
    # Store typed context object for subcommands
    ctx.obj = CLIContext(debug=debug)

    if debug:
        logger.debug("Debug mode enabled")


# =============================================================================
# Import Commands
# =============================================================================


@cli.group()
def import_data() -> None:
    """Import fragrance data from external sources."""


@import_data.command(name="kaggle")
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate without writing to database",
)
def import_kaggle(csv_file: Path, dry_run: bool) -> None:
    """Import fragrances from a Kaggle CSV file.

    CSV_FILE: Path to the CSV file to import.

    Expected columns: name, brand, concentration, year, gender, family,
    top_notes, heart_notes, base_notes, accords (flexible matching).
    """

    async def do_import() -> None:
        async with async_session_maker() as session:
            importer = KaggleImporter(session)

            click.echo(f"{'[DRY RUN] ' if dry_run else ''}Importing from {csv_file}...")

            result = await importer.import_csv(csv_file, dry_run=dry_run)

            if not dry_run:
                await session.commit()

            click.echo("\nImport Results:")
            click.echo(f"  Total rows: {result.total_rows}")
            click.echo(f"  Imported:   {result.imported}")
            click.echo(f"  Skipped:    {result.skipped}")

            if result.errors:
                click.echo(f"\nErrors ({len(result.errors)}):")
                for error in result.errors[:10]:  # Show first 10 errors
                    click.echo(f"  - {error}")
                if len(result.errors) > 10:
                    click.echo(f"  ... and {len(result.errors) - 10} more")

    try:
        run_async(do_import())
        logger.info(
            "Kaggle import completed",
            csv_file=str(csv_file),
            dry_run=dry_run,
        )
    except Exception as e:
        logger.exception("Kaggle import failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@import_data.command(name="parfumo-url")
@click.argument("url", type=str)
def import_parfumo_url(url: str) -> None:
    r"""Import a fragrance from its Parfumo URL.

    URL: Full Parfumo perfume page URL.

    Example: fragrance-rater import-data parfumo-url \
        "https://www.parfumo.com/Perfumes/brand/name"
    """

    async def do_import() -> None:
        async with async_session_maker() as session:
            scraper = ParfumoScraper(session)

            click.echo(f"Scraping {url}...")

            fragrance_id = await scraper.import_from_url(url)

            if fragrance_id:
                click.echo(f"Imported fragrance with ID: {fragrance_id}")
            else:
                click.echo("Failed to import fragrance. Check the URL.", err=True)
                sys.exit(1)

            scraper.close()

    try:
        run_async(do_import())
        logger.info("Parfumo URL import completed", url=url)
    except Exception as e:
        logger.exception("Parfumo import failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@import_data.command(name="parfumo-search")
@click.argument("query", type=str)
@click.option(
    "--import-first",
    is_flag=True,
    help="Automatically import the first result",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=5,
    help="Maximum search results to show",
)
def import_parfumo_search(
    query: str,
    import_first: bool,
    limit: int,
) -> None:
    """Search Parfumo and optionally import a fragrance.

    QUERY: Search terms (fragrance name, brand, or both).

    Args:
        query (str): Search terms (fragrance name, brand, or both).
        import_first (bool): Import the first search result automatically.
        limit (int): Maximum number of search results to display.

    Examples:
        fragrance-rater import-data parfumo-search "Aventus Creed"
        fragrance-rater import-data parfumo-search "Sauvage" --import-first
    """

    async def do_search() -> None:
        async with async_session_maker() as session:
            scraper = ParfumoScraper(session)

            click.echo(f"Searching Parfumo for '{query}'...")

            results = scraper.search(query, limit=limit)

            if not results:
                click.echo("No results found.")
                scraper.close()
                return

            click.echo(f"\nFound {len(results)} result(s):\n")

            for i, result in enumerate(results, 1):
                click.echo(f"  {i}. {result.name}")
                click.echo(f"     Brand: {result.brand}")
                click.echo(f"     URL: {result.url}\n")

            if import_first:
                click.echo(f"Importing first result: {results[0].name}...")
                fragrance_id = await scraper.import_from_url(results[0].url)

                if fragrance_id:
                    click.echo(f"Imported with ID: {fragrance_id}")
                else:
                    click.echo("Failed to import.", err=True)
                    sys.exit(1)
            else:
                click.echo(
                    "Use --import-first to automatically import the first result,"
                )
                click.echo(
                    "or use 'import-data parfumo-url <URL>' to import a specific one."
                )

            scraper.close()

    try:
        run_async(do_search())
        logger.info("Parfumo search completed", query=query)
    except Exception as e:
        logger.exception("Parfumo search failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Seed Commands
# =============================================================================


@cli.command(name="seed-reviewers")
def seed_reviewers() -> None:
    """Create default family reviewer profiles.

    Creates: Byron, Veronica, Bayden, Ariannah
    """

    async def do_seed() -> None:
        async with async_session_maker() as session:
            service = ReviewerService(session)
            reviewers = await service.seed_default_reviewers()
            await session.commit()

            click.echo("Created/verified reviewers:")
            for reviewer in reviewers:
                click.echo(f"  - {reviewer.name} (ID: {reviewer.id})")

    try:
        run_async(do_seed())
        logger.info("Seed reviewers completed")
    except Exception as e:
        logger.exception("Seed reviewers failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Profile Commands
# =============================================================================


@cli.command()
@click.argument("name", type=str)
def profile(name: str) -> None:
    """Show a reviewer's preference profile.

    NAME: Reviewer name to show profile for.
    """

    async def show_profile() -> None:
        async with async_session_maker() as session:
            service = ReviewerService(session)
            reviewer = await service.get_by_name(name)

            if not reviewer:
                click.echo(f"Reviewer '{name}' not found.", err=True)
                sys.exit(1)

            click.echo(f"\nProfile: {reviewer.name}")
            click.echo(f"ID: {reviewer.id}")
            click.echo(f"Created: {reviewer.created_at}")
            click.echo(f"Evaluations: {len(reviewer.evaluations)}")

            if reviewer.evaluations:
                ratings = [e.rating for e in reviewer.evaluations]
                avg_rating = sum(ratings) / len(ratings)
                click.echo(f"Average Rating: {avg_rating:.1f}/5")

    try:
        run_async(show_profile())
    except Exception as e:
        logger.exception("Profile command failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Utility Commands
# =============================================================================


@cli.command()
@click.option(
    "--name",
    "-n",
    type=str,
    default="World",
    help="Name to greet",
)
@click.pass_context
def hello(ctx: click.Context, name: str) -> None:
    """Greet the user with a personalized message."""
    try:
        cli_ctx: CLIContext = (
            ctx.obj if isinstance(ctx.obj, CLIContext) else CLIContext()
        )

        logger.info(
            "Processing hello command",
            name=name,
            debug=cli_ctx.debug,
        )

        message = f"Hello, {name}!"
        click.echo(message)

        logger.info("Command completed successfully", result=message)

    except Exception as e:
        logger.exception("Command failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Display current configuration settings.

    Shows configuration values from environment variables or defaults.
    """
    try:
        cli_ctx: CLIContext = (
            ctx.obj if isinstance(ctx.obj, CLIContext) else CLIContext()
        )

        logger.info("Retrieving configuration")

        click.echo("Current Configuration:")
        click.echo(f"  Project: {settings.project_name}")
        click.echo(f"  Version: {settings.version}")
        click.echo(f"  Debug: {cli_ctx.debug}")
        click.echo(f"  Log Level: {settings.log_level}")
        click.echo(f"  Database URL: {mask_database_url(settings.database_url)}")

        logger.info("Configuration displayed successfully")

    except Exception as e:
        logger.exception("Failed to display configuration", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
