"""Exercise the vocabulary foundation migration (000091664cdd) on SQLite.

Like the other per-migration tests, this builds the model's schema, applies the
migration's downgrade to reach the prior state, loads legacy-shaped rows, then
upgrades and checks both the schema and what happened to the data.
"""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, create_engine, inspect, text

from fragrance_rater.models import Base

_VERSIONS = Path(__file__).parents[2] / "alembic/versions"
_TABLES = (
    "notes",
    "note_aliases",
    "fragrance_notes",
    "accord_types",
    "fragrance_accords",
)


def _migration():
    path = next(_VERSIONS.glob("000091664cdd_*.py"))
    spec = importlib.util.spec_from_file_location(path.name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(connection, step):
    with Operations.context(MigrationContext.configure(connection)):
        step()


def _checks(inspector, table):
    return {
        check["name"]: " ".join(check["sqltext"].split())
        for check in inspector.get_check_constraints(table)
    }


def _modeled_checks(table):
    return {
        constraint.name: " ".join(str(constraint.sqltext).split())
        for constraint in Base.metadata.tables[table].constraints
        if isinstance(constraint, CheckConstraint)
    }


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migrate.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        _run(connection, _migration().downgrade)
    return engine


def _fragrance(connection, fragrance_id, data_source="manual"):
    connection.execute(
        text(
            "INSERT INTO fragrances (id, name, brand, concentration, version_key, "
            "gender_target, primary_family, subfamily, data_source, created_at, "
            "updated_at) VALUES (:id, :id, 'B', 'EDP', 'legacy', 'Unisex', "
            "'Woody', 'Dry Woods', :source, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"id": fragrance_id, "source": data_source},
    )


def _note(connection, note_id, name, category="Top"):
    connection.execute(
        text("INSERT INTO notes (id, name, category) VALUES (:id, :name, :category)"),
        {"id": note_id, "name": name, "category": category},
    )


def _link(connection, link_id, fragrance_id, note_id, position="top"):
    connection.execute(
        text(
            "INSERT INTO fragrance_notes (id, fragrance_id, note_id, position) "
            "VALUES (:id, :f, :n, :p)"
        ),
        {"id": link_id, "f": fragrance_id, "n": note_id, "p": position},
    )


def _accord(connection, fragrance_id, accord_type, intensity):
    connection.execute(
        text(
            "INSERT INTO fragrance_accords (fragrance_id, accord_type, intensity) "
            "VALUES (:f, :a, :i)"
        ),
        {"f": fragrance_id, "a": accord_type, "i": intensity},
    )


def test_downgrade_reaches_the_prior_schema(engine):
    inspector = inspect(engine)
    assert not {"note_aliases", "accord_types"} & set(inspector.get_table_names())
    assert "name_key" not in {c["name"] for c in inspector.get_columns("notes")}
    assert "rank" not in {c["name"] for c in inspector.get_columns("fragrance_notes")}
    assert "intensity_source" not in {
        c["name"] for c in inspector.get_columns("fragrance_accords")
    }


def test_upgrade_matches_the_models(engine):
    with engine.begin() as connection:
        _run(connection, _migration().upgrade)
    inspector = inspect(engine)
    for table in _TABLES:
        assert {c["name"] for c in inspector.get_columns(table)} == {
            c.name for c in Base.metadata.tables[table].columns
        }, table
        assert _checks(inspector, table) == _modeled_checks(table), table
    assert {
        fk["referred_table"] for fk in inspector.get_foreign_keys("fragrance_accords")
    } == {"fragrances", "accord_types"}
    notes = {c["name"]: c for c in inspector.get_columns("notes")}
    assert notes["category"]["nullable"] is True
    assert notes["name_key"]["nullable"] is False


def test_colliding_notes_merge_into_the_most_used_spelling(engine):
    with engine.begin() as connection:
        for fragrance_id in ("f1", "f2", "f3"):
            _fragrance(connection, fragrance_id)
        _note(connection, "n-spaced", "Oak Moss")
        _note(connection, "n-joined", "oakmoss")
        _note(connection, "n-caps", "OAKMOSS")
        _note(connection, "n-neroli", "Néroli", "Citrus")
        _link(connection, "l1", "f1", "n-spaced")
        _link(connection, "l2", "f2", "n-spaced")
        _link(connection, "l3", "f3", "n-joined")
        # f1 also links the spelling that will be absorbed, in the same position:
        # the duplicate is dropped rather than violating the unique link.
        _link(connection, "l4", "f1", "n-joined")
        _link(connection, "l5", "f2", "n-neroli", "heart")
        _link(connection, "l6", "f3", "n-spaced", "heart")
        _run(connection, _migration().upgrade)

    with engine.connect() as connection:
        notes = connection.execute(
            text("SELECT id, name, name_key, category FROM notes ORDER BY name_key")
        ).all()
        assert notes == [
            ("n-neroli", "Néroli", "neroli", "Citrus"),
            ("n-spaced", "Oak Moss", "oakmoss", None),
        ]
        links = connection.execute(
            text("SELECT fragrance_id, note_id FROM fragrance_notes ORDER BY id")
        ).all()
        assert links == [
            ("f1", "n-spaced"),
            ("f2", "n-spaced"),
            ("f3", "n-spaced"),
            ("f2", "n-neroli"),
            ("f3", "n-spaced"),
        ]
        aliases = connection.execute(
            text(
                "SELECT raw_label, alias_key, canonical_note_id, mapping_version, "
                "origin FROM note_aliases ORDER BY raw_label"
            )
        ).all()
        assert aliases == [
            ("OAKMOSS", "oakmoss", "n-spaced", "nm-v1", "observed"),
            ("oakmoss", "oakmoss", "n-spaced", "nm-v1", "observed"),
        ]


def test_equal_usage_keeps_the_lowest_id(engine):
    with engine.begin() as connection:
        _note(connection, "b", "Ylang-Ylang")
        _note(connection, "a", "Ylang Ylang")
        _run(connection, _migration().upgrade)
    with engine.connect() as connection:
        survivors = connection.execute(text("SELECT id, name FROM notes")).all()
        absorbed = connection.execute(
            text("SELECT raw_label, canonical_note_id FROM note_aliases")
        ).all()
    assert survivors == [("a", "Ylang Ylang")]
    assert absorbed == [("Ylang-Ylang", "a")]


def test_pyramid_positions_are_removed_from_note_category(engine):
    with engine.begin() as connection:
        for note_id, name, category in (
            ("a", "Bergamot", "Top"),
            ("b", "Rose", "heart"),
            ("c", "Amber", "BASE"),
            ("d", "Iris", "Floral"),
        ):
            _note(connection, note_id, name, category)
        _run(connection, _migration().upgrade)
    with engine.connect() as connection:
        categories = dict(
            connection.execute(text("SELECT id, category FROM notes")).all()
        )
    assert categories == {"a": None, "b": None, "c": None, "d": "Floral"}


def test_accords_are_normalized_and_flagged_by_source(engine):
    with engine.begin() as connection:
        _fragrance(connection, "kag", "kaggle")
        _fragrance(connection, "par", "parfumo")
        _fragrance(connection, "dup", "kaggle")
        # The importer's ladder: 1.0, 0.85, 0.7 by position.
        _accord(connection, "kag", "Woody", 1.0)
        _accord(connection, "kag", "Fresh Spicy", 0.85)
        _accord(connection, "kag", "Citrus", 0.1)
        # A Kaggle value off the ladder is a reported percentage.
        _accord(connection, "kag", "Musk", 0.9)
        # A non-Kaggle source's 0.85 is a measurement, whatever the number.
        _accord(connection, "par", "woody", 0.85)
        # Two spellings on one fragrance collapse to one row, keeping the larger.
        _accord(connection, "dup", "Amber", 0.4)
        _accord(connection, "dup", "amber", 0.9)
        # The survivor's provenance follows its own weight, in either order: here
        # the spelling that is already the code has the smaller, on-ladder weight.
        _fragrance(connection, "rev", "kaggle")
        _accord(connection, "rev", "Amber", 0.9)
        _accord(connection, "rev", "amber", 0.4)
        # ...and an on-ladder survivor is positional, with its own rank.
        _fragrance(connection, "lad", "kaggle")
        _accord(connection, "lad", "Woody", 1.0)
        _accord(connection, "lad", "woody", 0.4)
        _run(connection, _migration().upgrade)

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT fragrance_id, accord_type, intensity, intensity_source, rank "
                "FROM fragrance_accords ORDER BY fragrance_id, accord_type"
            )
        ).all()
        codes = connection.execute(
            text("SELECT code, label FROM accord_types ORDER BY code")
        ).all()
    assert rows == [
        ("dup", "amber", 0.9, "measured", None),
        ("kag", "citrus", 0.1, "positional", None),
        ("kag", "fresh spicy", 0.85, "positional", 1),
        ("kag", "musk", 0.9, "measured", None),
        ("kag", "woody", 1.0, "positional", 0),
        ("lad", "woody", 1.0, "positional", 0),
        ("par", "woody", 0.85, "measured", None),
        ("rev", "amber", 0.9, "measured", None),
    ]
    assert [code for code, _ in codes] == [
        "amber",
        "citrus",
        "fresh spicy",
        "musk",
        "woody",
    ]
    assert dict(codes)["fresh spicy"] == "Fresh Spicy"


def test_non_latin_note_names_keep_a_usable_key_and_stay_distinct(engine):
    with engine.begin() as connection:
        _note(connection, "zh", "中文")
        _note(connection, "ga", "が")
        _note(connection, "ka", "か")
        _note(connection, "ne", "Néroli")
        _run(connection, _migration().upgrade)
    with engine.connect() as connection:
        keys = dict(connection.execute(text("SELECT id, name_key FROM notes")).all())
    assert keys == {"zh": "中文", "ga": "が", "ka": "か", "ne": "neroli"}


def test_a_stray_position_blocks_the_upgrade(engine):
    with engine.begin() as connection:
        _fragrance(connection, "f1")
        _note(connection, "n1", "Rose")
        _link(connection, "l1", "f1", "n1", "middle")
    with pytest.raises(RuntimeError, match="position"), engine.begin() as connection:
        _run(connection, _migration().upgrade)


def test_downgrade_refuses_to_drop_curated_aliases(engine):
    with engine.begin() as connection:
        _note(connection, "n1", "Vanilla")
        _run(connection, _migration().upgrade)
        connection.execute(
            text(
                "INSERT INTO note_aliases (id, raw_label, alias_key, "
                "canonical_note_id, mapping_version, origin) VALUES "
                "('a1', 'vanille', 'vanille', 'n1', 'nm-v1', 'curated')"
            )
        )
    with pytest.raises(RuntimeError, match="curated"), engine.begin() as connection:
        _run(connection, _migration().downgrade)

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM note_aliases"))
        _run(connection, _migration().downgrade)
    assert "note_aliases" not in inspect(engine).get_table_names()
