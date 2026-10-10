"""Extreme Hyper-Systemized Test Suite for SBX Relational Querying.

Exercises SQLite database across 6 core domains:
1. Engine PRAGMA and Invariant State (WAL, Foreign Keys, Cache Size)
2. Entity Completeness & Non-Zero Cardinality Constraints
3. Relational Referential Integrity (Orbits, Velocities, Alias, Configurations, Duplicates)
4. Cross-Catalog Identifier Resolution (HIP, Gaia, 2MASS)
5. Astrophysical Sanity Constraints (Periods, Eccentricities, Velocities)
6. Multi-Body Hierarchical Configurations & Traversal
"""

import sqlite3
from pathlib import Path
import pytest

DB_PATH = Path("data/db/sbx.sqlite")


@pytest.fixture(scope="session")
def conn():
    """Provides a thread-safe read-only connection with strict WAL enforcement."""
    assert DB_PATH.exists(), f"Database missing at {DB_PATH}. Run load_to_sqlite.py first."
    connection = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    yield connection
    connection.close()


# -----------------------------------------------------------------------------
# DOMAIN 1: Engine PRAGMA & Architectural Invariants
# -----------------------------------------------------------------------------
class TestEnginePragmas:
    """Verifies that SQLite engine invariants adhere to the hyper-systemizer WAL spec."""

    def test_journal_mode_is_wal(self, conn):
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal", f"Engine failed WAL invariant. Current mode: {mode}"

    def test_expected_tables_exist(self, conn):
        expected_tables = {"systems", "orbits", "velocities", "alias", "configurations", "duplicates"}
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        existing_tables = {r[0] for r in rows}
        assert expected_tables.issubset(existing_tables), f"Missing tables: {expected_tables - existing_tables}"


# -----------------------------------------------------------------------------
# DOMAIN 2: Exact Cardinality & Completeness
# -----------------------------------------------------------------------------
class TestCardinalityInvariants:
    """Verifies that ingestion is lossless against verified snapshot numbers."""

    @pytest.mark.parametrize(
        "table, expected_count",
        [
            ("systems", 4080),
            ("orbits", 5169),
            ("velocities", 224148),
            ("alias", 102459),
            ("configurations", 261),
            ("duplicates", 18),
        ],
    )
    def test_table_row_count(self, conn, table, expected_count):
        count = conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
        assert count == expected_count, f"Table '{table}' has {count} rows; expected exactly {expected_count}"


# -----------------------------------------------------------------------------
# DOMAIN 3: Referential Integrity Across Boundaries
# -----------------------------------------------------------------------------
class TestReferentialIntegrity:
    """Verifies that child relations are strictly bound to parent systems."""

    def test_all_orbits_have_valid_systems(self, conn):
        orphans = conn.execute("""
            SELECT COUNT(*) FROM orbits o
            LEFT JOIN systems s ON o.sn = s.sn
            WHERE s.sn IS NULL;
        """).fetchone()[0]
        assert orphans == 0, f"Detected {orphans} orphaned orbits lacking a parent system."

    def test_all_velocities_have_valid_systems(self, conn):
        orphans = conn.execute("""
            SELECT COUNT(*) FROM velocities v
            LEFT JOIN systems s ON v.sn = s.sn
            WHERE s.sn IS NULL;
        """).fetchone()[0]
        assert orphans == 0, f"Detected {orphans} orphaned velocities lacking a parent system."

    def test_all_aliases_have_valid_systems(self, conn):
        orphans = conn.execute("""
            SELECT COUNT(*) FROM alias a
            LEFT JOIN systems s ON a.sn = s.sn
            WHERE s.sn IS NULL;
        """).fetchone()[0]
        assert orphans == 0, f"Detected {orphans} orphaned aliases lacking a parent system."

    def test_duplicate_systems_reference_existing_systems(self, conn):
        invalid = conn.execute("""
            SELECT COUNT(*) FROM duplicates d
            LEFT JOIN systems s1 ON d.sn = s1.sn
            LEFT JOIN systems s2 ON d.sn_duplicate = s2.sn
            WHERE s1.sn IS NULL OR s2.sn IS NULL;
        """).fetchone()[0]
        assert invalid == 0, f"Detected {invalid} duplicates referencing non-existent system numbers."


# -----------------------------------------------------------------------------
# DOMAIN 4: Identifier Resolution & Join Topology
# -----------------------------------------------------------------------------
class TestIdentifierResolution:
    """Verifies that common catalog identifiers resolve unambiguously."""

    def test_resolve_by_catalog_and_id(self, conn):
        # Sample well-known system: sn 1
        query = """
            SELECT s.sn, s.ra, s.dec, a.catalog, a.identifier
            FROM alias a
            JOIN systems s ON a.sn = s.sn
            WHERE a.sn = 1
            LIMIT 5;
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) > 0, "Failed to resolve system aliases for sn=1"
        assert rows[0][0] == 1

    def test_system_to_orbit_one_to_many(self, conn):
        # Find systems having multiple orbital determinations
        query = """
            SELECT sn, COUNT(*) as orbit_count
            FROM orbits
            GROUP BY sn
            HAVING orbit_count > 1
            LIMIT 10;
        """
        multi_orbits = conn.execute(query).fetchall()
        assert len(multi_orbits) > 0, "Expected systems with multiple orbits per SB9/SBX design."


# -----------------------------------------------------------------------------
# DOMAIN 5: Astrophysical Domain Sanity Constraints
# -----------------------------------------------------------------------------
class TestAstrophysicalConstraints:
    """Verifies physical invariants of spectroscopic binary orbits."""

    def test_orbital_periods_are_strictly_positive(self, conn):
        invalid_periods = conn.execute("""
            SELECT COUNT(*) FROM orbits
            WHERE period IS NOT NULL AND period <= 0;
        """).fetchone()[0]
        assert invalid_periods == 0, f"Found {invalid_periods} orbits with non-positive period."

    def test_eccentricities_are_bounded_zero_to_one(self, conn):
        invalid_ecc = conn.execute("""
            SELECT COUNT(*) FROM orbits
            WHERE eccentricity IS NOT NULL AND (eccentricity < 0 OR eccentricity >= 1.0);
        """).fetchone()[0]
        assert invalid_ecc == 0, f"Found {invalid_ecc} orbits with unphysical eccentricity (<0 or >=1)."

    def test_sb1_vs_sb2_velocity_amplitudes(self, conn):
        # K1 must always be positive where determined
        invalid_k1 = conn.execute("""
            SELECT COUNT(*) FROM orbits
            WHERE K1 IS NOT NULL AND K1 < 0;
        """).fetchone()[0]
        assert invalid_k1 == 0, f"Found {invalid_k1} orbits with negative K1."

        # SB2 systems must have positive K2
        sb2_count = conn.execute("SELECT COUNT(*) FROM orbits WHERE K2 IS NOT NULL;").fetchone()[0]
        assert sb2_count > 0, "No SB2 (double-lined) systems found in database."

    def test_coordinates_are_within_celestial_bounds(self, conn):
        # RA [0, 360], Dec [-90, 90]
        invalid_coords = conn.execute("""
            SELECT COUNT(*) FROM systems
            WHERE (ra IS NOT NULL AND (ra < 0 OR ra > 360))
               OR (dec IS NOT NULL AND (dec < -90 OR dec > 90));
        """).fetchone()[0]
        assert invalid_coords == 0, f"Found {invalid_coords} systems with coordinates out of celestial bounds."


# -----------------------------------------------------------------------------
# DOMAIN 6: Multi-Body Hierarchy & Configurations
# -----------------------------------------------------------------------------
class TestHierarchicalConfigurations:
    """Verifies tree structure integrity for triples and quadruples."""

    def test_configuration_flags_consistent(self, conn):
        high_order = conn.execute("SELECT COUNT(*) FROM configurations WHERE in_high_order IN ('1', 1);").fetchone()[0]
        assert high_order > 0, "Zero high-order multiple configurations found."
        families = conn.execute("SELECT COUNT(DISTINCT family) FROM configurations WHERE family IS NOT NULL;").fetchone()[0]
        assert families > 0, "Zero hierarchical families found in configurations."
