"""Command-line interface for Fragrance Rater.

Provides commands for common operations and demonstrates Click best practices
with structured logging integration.
"""

import sys
from dataclasses import dataclass

import click
from structlog.stdlib import BoundLogger

from fragrance_rater.core.config import settings
from fragrance_rater.utils.logging import get_logger

logger: BoundLogger = get_logger(__name__)


@dataclass
class CLIContext:
    """Typed context object for Click commands."""

    debug: bool = False


@click.group()
@click.version_option(version="0.1.0", prog_name="fragrance-rater")
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """Fragrance Rater - Personal fragrance evaluation and recommendation system for family use with LLM-powered recommendations."""
    # Store typed context object for subcommands
    ctx.obj = CLIContext(debug=debug)

    if debug:
        logger.debug("Debug mode enabled")


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
        click.echo("  Project: Fragrance Rater")
        click.echo("  Version: 0.1.0")
        click.echo(f"  Debug: {cli_ctx.debug}")
        click.echo(f"  Log Level: {settings.log_level}")

        logger.info("Configuration displayed successfully")

    except Exception as e:
        logger.exception("Failed to display configuration", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
