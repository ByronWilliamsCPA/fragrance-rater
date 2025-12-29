"""Command-line interface for Fragrance Rater.

Provides commands for common operations and demonstrates Click best practices
with structured logging integration.
"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import click
from structlog.stdlib import BoundLogger

from fragrance_rater.core.config import settings
from fragrance_rater.utils.logging import get_logger

logger: BoundLogger = get_logger(__name__)


@dataclass
class CLIContext:
    """Typed context object for Click commands."""

    debug: bool = False


def run_async(coro):  # noqa: ANN001, ANN201
    """Run an async coroutine in a new event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


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
@click.pass_context
def import_kaggle(ctx: click.Context, csv_file: Path, dry_run: bool) -> None:
    """Import fragrances from a Kaggle CSV file.

    CSV_FILE: Path to the CSV file to import.

    Expected columns: name, brand, concentration, year, gender, family,
    top_notes, heart_notes, base_notes, accords (flexible matching).
    """
    from fragrance_rater.core.database import async_session_maker
    from fragrance_rater.services.kaggle_importer import KaggleImporter

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


# =============================================================================
# Seed Commands
# =============================================================================


@cli.command(name="seed-reviewers")
@click.pass_context
def seed_reviewers(ctx: click.Context) -> None:
    """Create default family reviewer profiles.

    Creates: Byron, Veronica, Bayden, Ariannah
    """
    from fragrance_rater.core.database import async_session_maker
    from fragrance_rater.services.reviewer_service import ReviewerService

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
@click.pass_context
def profile(ctx: click.Context, name: str) -> None:
    """Show a reviewer's preference profile.

    NAME: Reviewer name to show profile for.
    """
    from fragrance_rater.core.database import async_session_maker
    from fragrance_rater.services.reviewer_service import ReviewerService

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
        click.echo(f"  Database URL: {settings.database_url[:50]}...")

        logger.info("Configuration displayed successfully")

    except Exception as e:
        logger.exception("Failed to display configuration", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
