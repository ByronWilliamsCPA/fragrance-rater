"""Persist provider-reported OpenRouter token and cost accounting.

Revision ID: f5c2d3e4a5b6
Revises: e4b1c2d3f4a5
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5c2d3e4a5b6"
down_revision: str | None = "e4b1c2d3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add optional provider usage fields without inventing missing costs."""
    op.add_column("llm_invocations", sa.Column("prompt_tokens", sa.Integer()))
    op.add_column("llm_invocations", sa.Column("completion_tokens", sa.Integer()))
    op.add_column("llm_invocations", sa.Column("total_tokens", sa.Integer()))
    op.add_column("llm_invocations", sa.Column("provider_cost_credits", sa.Float()))
    op.create_check_constraint(
        "ck_llm_invocations_prompt_tokens_nonnegative",
        "llm_invocations",
        "prompt_tokens IS NULL OR prompt_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_llm_invocations_completion_tokens_nonnegative",
        "llm_invocations",
        "completion_tokens IS NULL OR completion_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_llm_invocations_total_tokens_nonnegative",
        "llm_invocations",
        "total_tokens IS NULL OR total_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_llm_invocations_provider_cost_nonnegative",
        "llm_invocations",
        "provider_cost_credits IS NULL OR provider_cost_credits >= 0",
    )


def downgrade() -> None:
    """Remove provider usage fields while preserving invocation records."""
    op.drop_constraint(
        "ck_llm_invocations_provider_cost_nonnegative",
        "llm_invocations",
        type_="check",
    )
    op.drop_constraint(
        "ck_llm_invocations_total_tokens_nonnegative",
        "llm_invocations",
        type_="check",
    )
    op.drop_constraint(
        "ck_llm_invocations_completion_tokens_nonnegative",
        "llm_invocations",
        type_="check",
    )
    op.drop_constraint(
        "ck_llm_invocations_prompt_tokens_nonnegative",
        "llm_invocations",
        type_="check",
    )
    op.drop_column("llm_invocations", "provider_cost_credits")
    op.drop_column("llm_invocations", "total_tokens")
    op.drop_column("llm_invocations", "completion_tokens")
    op.drop_column("llm_invocations", "prompt_tokens")
