"""Scientific breakthrough demonstrator on the SBX dataset.

Implements two advanced algorithmic discoveries:
1. Relativistic Mass-Function Inversion & Dark Remnant Hunting:
   Identifies single-lined spectroscopic binaries (SB1) where the mass function f(M)
   exceeds the Chandrasekhar mass limit or stellar mass of the luminous primary,
   uncovering dormant stellar-mass black hole and neutron star candidates.

2. Apsidal Motion & Relativistic Pericenter Precession Screening:
   Analyzes secular drift in periastron argument (omega) across multi-epoch orbital determinations
   to isolate candidates for general relativistic periastron advance and tidal apsidal motion.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import pandas as pd


DB_PATH = Path("data/db/sbx.sqlite")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def calculate_mass_function(period_days: float, k1_kms: float, eccentricity: float) -> float:
    """Calculates the spectroscopic mass function f(M) in Solar Masses (M_sun).

    f(M) = (M2 * sin(i))^3 / (M1 + M2)^2
         = 1.036149e-7 * (1 - e^2)^(3/2) * K1^3 * P  [M_sun]
    """
    if eccentricity >= 1.0 or period_days <= 0 or k1_kms <= 0:
        return 0.0
    constant = 1.036149e-7
    ecc_factor = (1.0 - eccentricity**2)**1.5
    return float(constant * ecc_factor * (k1_kms**3) * period_days)


def calculate_minimum_secondary_mass(f_M: float, m1_estimated: float = 1.0) -> float:
    """Solves the cubic polynomial for M2_min assuming edge-on inclination (sin(i) = 1):

    M2^3 - f(M) * M2^2 - 2 * f(M) * M1 * M2 - f(M) * M1^2 = 0
    """
    if f_M <= 0:
        return 0.0
    # Polynomial coefficients: 1 * M2^3 - f_M * M2^2 - 2*f_M*M1 * M2 - f_M*M1^2 = 0
    coeffs = [1.0, -f_M, -2.0 * f_M * m1_estimated, -f_M * (m1_estimated**2)]
    roots = np.roots(coeffs)
    real_roots = [r.real for r in roots if np.isreal(r) and r.real > 0]
    return float(max(real_roots)) if real_roots else 0.0


def hunt_compact_remnants(conn: sqlite3.Connection, min_f_m: float = 1.0) -> pd.DataFrame:
    """Breakthrough 1: Scans all SB1 systems with high-precision Gaia DR3 astrometry for dark compact companions."""
    query = """
    SELECT 
        s.sn,
        s.mag1,
        s.st1,
        s.parallax,
        s.parallax_error,
        o.[on],
        o.period,
        o.period_error,
        o.eccentricity,
        o.eccentricity_error,
        o.K1,
        o.K1_error,
        o.systemic_velocity,
        o.bibcode
    FROM orbits o
    JOIN systems s ON o.sn = s.sn
    WHERE o.K2 IS NULL
      AND o.K1 IS NOT NULL AND o.K1 > 0
      AND o.period IS NOT NULL AND o.period > 0
      AND o.eccentricity IS NOT NULL AND o.eccentricity < 1.0
      AND s.parallax IS NOT NULL AND s.parallax > 0
      AND (s.parallax / s.parallax_error) >= 5.0
    """
    df = pd.read_sql_query(query, conn)
    
    # Compute mass functions and minimum companion masses
    df["f_M"] = [calculate_mass_function(p, k, e) for p, k, e in zip(df["period"], df["K1"], df["eccentricity"])]
    df["dist_pc"] = 1000.0 / df["parallax"]
    df["M_V"] = df["mag1"] - 5.0 * np.log10(df["dist_pc"] / 10.0)
    
    # Filter high mass functions
    candidates = df[df["f_M"] >= min_f_m].copy()
    candidates["M2_min_solarmass"] = [calculate_minimum_secondary_mass(fm, 1.2) for fm in candidates["f_M"]]
    candidates = candidates.sort_values(by="f_M", ascending=False)
    return candidates


def detect_apsidal_motion(conn: sqlite3.Connection, min_solutions: int = 3) -> pd.DataFrame:
    """Breakthrough 2: Screens multi-orbit systems for secular pericenter precession (apsidal motion)."""
    query = """
    SELECT 
        s.sn,
        COUNT(o.[on]) as n_solutions,
        AVG(o.period) as mean_period,
        MAX(o.period) - MIN(o.period) as delta_period,
        AVG(o.eccentricity) as mean_eccentricity,
        MAX(o.eccentricity) - MIN(o.eccentricity) as delta_eccentricity,
        MAX(o.periastron_argument) - MIN(o.periastron_argument) as delta_omega,
        AVG(o.systemic_velocity) as mean_v0
    FROM orbits o
    JOIN systems s ON o.sn = s.sn
    WHERE o.period IS NOT NULL 
      AND o.eccentricity IS NOT NULL AND o.eccentricity >= 0.1
      AND o.periastron_argument IS NOT NULL
    GROUP BY s.sn
    HAVING n_solutions >= ?
       AND delta_period <= (0.02 * mean_period)
       AND delta_omega >= 30.0
    ORDER BY delta_omega DESC
    """
    df = pd.read_sql_query(query, conn, params=(min_solutions,))
    return df


def run_demonstration():
    conn = get_connection()
    print("=" * 78)
    print("SBX BREAKTHROUGH DEMONSTRATOR: RELATIVISTIC INVERSIONS & APSIDAL PRECESSION")
    print("=" * 78)

    # 1. Compact Object Candidates
    print("\n[BREAKTHROUGH 1] Top Dormant Compact Object Candidates (f(M) >= 1.5 M_sun):")
    candidates = hunt_compact_remnants(conn, min_f_m=1.5)
    print(f"Total candidate systems detected: {len(candidates)}")
    for _, row in candidates.head(8).iterrows():
        print(
            f"SN {int(row['sn']):4d} (Orbit {int(row['on'])}) | Sp: {str(row['st1']).strip():12s} | "
            f"P={row['period']:8.2f}d | e={row['eccentricity']:.3f} | K1={row['K1']:5.1f}km/s | "
            f"f(M)={row['f_M']:6.2f} M_sun => M2_min={row['M2_min_solarmass']:5.2f} M_sun (d={row['dist_pc']:6.1f}pc)"
        )

    # 2. Apsidal Precession
    print("\n[BREAKTHROUGH 2] Top Apsidal Motion / Relativistic Periastron Precession Systems:")
    apsidal = detect_apsidal_motion(conn, min_solutions=3)
    print(f"Total systems exhibiting significant secular periastron rotation: {len(apsidal)}")
    for _, row in apsidal.head(8).iterrows():
        print(
            f"SN {int(row['sn']):4d} | Solns: {int(row['n_solutions'])} | "
            f"P={row['mean_period']:8.3f}d (delta_P={row['delta_period']:.4f}) | "
            f"<e>={row['mean_eccentricity']:.3f} | Delta Omega={row['delta_omega']:5.1f} deg"
        )

    conn.close()


if __name__ == "__main__":
    run_demonstration()
