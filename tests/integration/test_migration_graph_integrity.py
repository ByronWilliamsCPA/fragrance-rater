"""Guard the Alembic migration graph itself: unique revision ids, one head.

This complements the per-migration tests (e.g.
``test_ml_prediction_snapshots_migration.py``), which exercise individual
upgrade/downgrade behavior but never validate the graph as a whole. Without
this check, a future PR reusing a colliding literal revision id (the exact
failure mode that produced the `a1b2c3d4e5f6` collision between the
`ml_prediction_snapshots` and `fragella_lookups` migrations, and that PR #78
was about to repeat with a third file) would not be caught until `alembic
history`/`alembic heads` was run by hand and its warning noticed.
"""

from alembic.config import Config
from alembic.script import ScriptDirectory


def _script_directory() -> ScriptDirectory:
    config = Config("alembic.ini")
    return ScriptDirectory.from_config(config)


def test_migration_revision_ids_are_unique():
    """No two migration files may declare the same revision id.

    ``ScriptDirectory.walk_revisions`` silently tolerates duplicate ids at
    the Python-object level; the collision only surfaces as an
    ``alembic history`` resolution failure or an ``alembic heads`` warning
    that picks one file by directory-listing order. Enumerate revisions
    directly from the directory instead, so a duplicate is a hard test
    failure rather than a runtime warning someone has to notice.
    """
    script_dir = _script_directory()
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for script in script_dir.walk_revisions():
        if script.revision in seen:
            prior_path = seen[script.revision]
            duplicates.append(
                f"{script.revision!r} used by both {prior_path!r} and {script.path!r}"
            )
        else:
            seen[script.revision] = script.path

    assert not duplicates, "Duplicate Alembic revision id(s):\n" + "\n".join(duplicates)


def test_migration_graph_has_exactly_one_head():
    """The migration graph must resolve to a single linear head.

    A second head (from a duplicate revision id, a mis-chained
    ``down_revision``, or a genuine unintended branch) breaks
    ``alembic upgrade head`` for any environment that doesn't opt into
    ``heads`` (plural), which this project does not otherwise need.
    """
    script_dir = _script_directory()
    heads = script_dir.get_heads()
    assert len(heads) == 1, (
        f"Expected exactly one Alembic head, found {len(heads)}: {heads}. "
        "A duplicate revision id or a mis-chained down_revision usually causes this."
    )
