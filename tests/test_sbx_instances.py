"""Extreme Hyper-Systemized Instance Test Suite for SBX Database.

Exercises actual data instances across 5 discrete complexity levels:
- Level 1 [Mundane / Layman]: Identifier resolution, basic naked-eye filters, coordinate lookup.
- Level 2 [Target Selection & Observational Planning]: Brightness thresholds, declination limits, high proper motion.
- Level 3 [Standard Astrophysical Characterization]: Circular orbits, period distributions, SB1 vs. SB2 binaries.
- Level 4 [Statistical & High-Precision Kinematics]: Gaia DR3 distance cuts (<10 pc), extreme eccentricities (e >= 0.85), dense radial velocity curves.
- Level 5 [Exquisite / Cutting-Edge Astrophysical Research]: Hierarchical multiple stars, high mass functions, and multi-solution comparisons.
"""

import sqlite3
from pathlib import Path
import pytest

DB_PATH = Path("data/db/sbx.sqlite")


@pytest.fixture(scope="session")
def conn():
    """Provides a read-only connection to the SQLite database."""
    assert DB_PATH.exists(), f"Database not found at {DB_PATH}"
    connection = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    yield connection
    connection.close()


# -----------------------------------------------------------------------------
# LEVEL 1: Mundane / Layman Queries
# -----------------------------------------------------------------------------
class TestLevel1LaymanQueries:
    """Mundane searches: finding an object by common name or brightness for stargazing."""

    def test_find_system_by_common_catalog_identifier(self, conn):
        """Layman query: 'Tell me about HIP 443'."""
        query = """
            SELECT s.sn, s.ra, s.dec, a.catalog, a.identifier
            FROM alias a
            JOIN systems s ON a.sn = s.sn
            WHERE a.identifier = '443' AND a.catalog = 'HIP'
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) >= 1
        assert rows[0][0] == 1  # sn = 1

    def test_naked_eye_visible_stars(self, conn):
        """Layman query: 'Find all spectroscopic binaries visible to the naked eye (V <= 6.0)'."""
        query = """
            SELECT sn, mag1, st1
            FROM systems
            WHERE mag1 IS NOT NULL AND mag1 <= 6.0
            ORDER BY mag1 ASC
        """
        rows = conn.execute(query).fetchall()
        # Naked eye stars must be well-represented in SBX
        assert len(rows) > 500, f"Expected > 500 naked eye binaries, found {len(rows)}"
        # Brightest must have V < 3.0
        assert rows[0][1] < 3.0


# -----------------------------------------------------------------------------
# LEVEL 2: Observational Planning & Target Selection
# -----------------------------------------------------------------------------
class TestLevel2ObservationalPlanning:
    """Queries for telescope time proposals, visibility windows, and survey selection."""

    def test_northern_hemisphere_bright_observational_targets(self, conn):
        """Target selection: 'Northern stars (Dec > 20) with V < 8.0 suitable for small observatories'."""
        query = """
            SELECT s.sn, s.ra, s.dec, s.mag1, o.[on], o.period
            FROM systems s
            JOIN orbits o ON s.sn = o.sn
            WHERE s.dec > 20.0 AND s.mag1 < 8.0 AND o.period IS NOT NULL
            LIMIT 50
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) == 50
        assert all(r[2] > 20.0 and r[3] < 8.0 for r in rows)

    def test_high_proper_motion_nearby_systems(self, conn):
        """Kinematic target filter: 'Systems with total proper motion > 500 mas/yr'."""
        query = """
            SELECT sn, pmra, pmdec, (pmra*pmra + pmdec*pmdec) as total_pm_sq
            FROM systems
            WHERE pmra IS NOT NULL AND pmdec IS NOT NULL
              AND (pmra*pmra + pmdec*pmdec) > 250000.0 -- 500^2 mas/yr
            ORDER BY total_pm_sq DESC
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) > 0, "Expected fast-moving kinematic binaries in SBX."


# -----------------------------------------------------------------------------
# LEVEL 3: Standard Astrophysical Characterization
# -----------------------------------------------------------------------------
class TestLevel3StandardAstrophysics:
    """Standard binary star properties: periods, circularization, and single vs. double lined."""

    def test_circularized_short_period_binaries(self, conn):
        """Astrophysical check: 'Find tidally circularized orbits (e = 0) with short periods (P < 10 days)'."""
        query = """
            SELECT sn, [on], period, eccentricity
            FROM orbits
            WHERE eccentricity = 0.0 AND period < 10.0
            ORDER BY period ASC
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) > 100, f"Expected >100 circularized close binaries, found {len(rows)}"
        assert rows[0][3] == 0.0

    def test_double_lined_spectroscopic_binaries_sb2_ratio(self, conn):
        """Mass ratio calculation: 'Retrieve SB2 systems with measured velocity amplitudes K1 and K2'."""
        query = """
            SELECT sn, [on], K1, K2, (K1 / K2) as mass_ratio_estimate
            FROM orbits
            WHERE K1 IS NOT NULL AND K2 IS NOT NULL AND K1 > 0 AND K2 > 0
            LIMIT 100
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) == 100
        assert all(r[4] > 0 for r in rows)


# -----------------------------------------------------------------------------
# LEVEL 4: High-Precision Kinematics & Statistical Outliers
# -----------------------------------------------------------------------------
class TestLevel4StatisticalKinematics:
    """Deep kinematic cuts, extreme geometries, and extensive RV datasets."""

    def test_solar_neighborhood_systems_within_10_parsecs(self, conn):
        """Astrometric cut: 'Identify solar neighborhood systems (parallax > 100 mas, d < 10 pc)'."""
        query = """
            SELECT s.sn, s.parallax, s.parallax_error, a.catalog, a.identifier
            FROM systems s
            JOIN alias a ON s.sn = a.sn
            WHERE s.parallax > 100.0 AND a.catalog = 'Gaia'
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) > 0, "Expected solar neighborhood binaries in Gaia cross-match."
        assert all(r[1] > 100.0 for r in rows)

    def test_extreme_eccentricity_outliers(self, conn):
        """Orbital dynamics: 'Locate highly eccentric systems with e >= 0.85'."""
        query = """
            SELECT sn, [on], period, eccentricity, K1
            FROM orbits
            WHERE eccentricity >= 0.85
            ORDER BY eccentricity DESC
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) >= 5, "Expected extreme eccentricity outliers in SBX."
        assert rows[0][3] >= 0.85

    def test_dense_radial_velocity_curves(self, conn):
        """Time-series analysis: 'Identify orbits supported by > 300 individual RV observations'."""
        query = """
            SELECT v.sn, v.[on], COUNT(*) as rv_count, o.period, o.eccentricity
            FROM velocities v
            JOIN orbits o ON v.sn = o.sn AND v.[on] = o.[on]
            GROUP BY v.sn, v.[on]
            HAVING rv_count > 300
            ORDER BY rv_count DESC
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) > 0, "Expected orbits with high-cadence RV series."
        assert rows[0][2] > 300


# -----------------------------------------------------------------------------
# LEVEL 5: Exquisite / Cutting-Edge Astrophysical Research
# -----------------------------------------------------------------------------
class TestLevel5ExquisiteResearch:
    """Complex multi-body systems, competing historical solutions, and mass functions."""

    def test_hierarchical_higher_order_systems_with_orbits(self, conn):
        """Multi-body dynamics: 'Hierarchical triple or quadruple systems with measured orbital solutions'."""
        query = """
            SELECT c.sn, c.family, c.parent, c.child1, c.child2, COUNT(o.[on]) as orbit_solutions
            FROM configurations c
            JOIN orbits o ON c.sn = o.sn
            WHERE c.in_high_order IN ('1', 1)
            GROUP BY c.sn, c.family
            HAVING orbit_solutions >= 1
            ORDER BY orbit_solutions DESC
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) > 0, "Expected higher order multiple star configurations with orbits."

    def test_multi_orbit_evolutionary_discordance(self, conn):
        """Historical astronomy: 'Systems with >= 4 distinct published orbital determinations'."""
        query = """
            SELECT s.sn, COUNT(o.[on]) as num_solutions,
                   MIN(o.period) as min_P, MAX(o.period) as max_P
            FROM systems s
            JOIN orbits o ON s.sn = o.sn
            GROUP BY s.sn
            HAVING num_solutions >= 4
            ORDER BY num_solutions DESC
            LIMIT 10
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) > 0, "Expected systems with >= 4 competing orbital determinations."
        assert rows[0][1] >= 4

    def test_high_mass_function_compact_object_candidates(self, conn):
        """Relativistic candidate search: 'SB1 systems with long period (P > 30 d) and massive K1 (> 40 km/s)'."""
        query = """
            SELECT s.sn, s.mag1, s.st1, o.period, o.K1, o.eccentricity, o.bibcode
            FROM orbits o
            JOIN systems s ON o.sn = s.sn
            WHERE o.K2 IS NULL
              AND o.period > 30.0
              AND o.K1 > 40.0
            ORDER BY o.K1 DESC
            LIMIT 15
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) > 0, "Expected candidates for compact object companions."
        assert rows[0][3] > 30.0 and rows[0][4] > 40.0
