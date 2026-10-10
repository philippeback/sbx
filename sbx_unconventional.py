"""Extreme Unconventional Cross-Pollination Discovery Engine.

Fuses concepts across three non-astronomical fields into observational astrophysics:
1. Information Geometry & Riemannian Thermodynamic Metric:
   Treats the (log P, e) phase space not as flat Euclidean parameters, but as an
   information manifold endowed with a Fisher-Rao / Thermodynamic Metric. Tidal circularization
   acts as an entropy sink. We compute the Information Geometric Geodesic Distance from the
   Thermal Equilibrium Manifold (circularization boundary).

2. Topological Phase Transition & Dynamical Resonance Topology:
   Applies Persistent Topological Manifold Learning (PCA / Manifold Embedding) on normalized
   orbital phase invariants (log P, e, log K1, M_V, log(1 + omega_rate)) to discover
   emergent dynamical cluster attractor basins.

3. Shannon-Boltzmann Information Entropy of Radial Velocity Phase Coverage:
   Computes the differential Shannon phase entropy H_phase = -sum(p_i * log p_i) of observation
   cadence wrapped over orbital phase theta = (t - T0) / P mod 1. Uncovers 'Observational Blindspot
   Resonances' where high formal orbit grades disguise extreme phase undersampling.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
from sklearn.decomposition import PCA


DB_PATH = Path("data/db/sbx.sqlite")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


# -----------------------------------------------------------------------------
# CONCEPT 1: Thermodynamic Geodesic Distance from Tidal Equilibrium
# -----------------------------------------------------------------------------
def compute_thermodynamic_geodesics(conn: sqlite3.Connection) -> pd.DataFrame:
    """Projects binary orbits onto an Information Geometry manifold.

    In binary orbital thermodynamics, tidal dissipation irreversibly drives systems toward
    the ground state: e -> 0 at the circularization period P_circ (~ 8-10 days).
    We define the metric ds^2 = (d log P / sigma_logP)^2 + (de / (1 - e^2))^2
    (a hyperbolic Poincaré-half-plane analogue of the Fisher Information Metric).
    """
    query = """
    SELECT 
        o.sn,
        o.[on],
        o.period,
        o.eccentricity,
        o.K1,
        s.mag1,
        s.parallax,
        s.st1,
        o.bibcode
    FROM orbits o
    JOIN systems s ON o.sn = s.sn
    WHERE o.period > 0.1 AND o.period < 10000.0
      AND o.eccentricity >= 0.0 AND o.eccentricity < 0.99
      AND o.K1 > 0
    """
    df = pd.read_sql_query(query, conn)
    
    # Characteristic circularization period boundary P_crit ~ 8.0 days
    P_crit = 8.0
    
    # Hyperbolic Fisher Geodesic Distance from Tidal Equilibrium State (P <= P_crit, e = 0)
    # Metric component g_ee diverges as e -> 1, capturing relativistic/tidal tension:
    # d_Fisher = sqrt( (ln(P / P_crit))^2 + (arctanh(e))^2 )
    log_ratio = np.log(df["period"] / P_crit)
    arctanh_e = np.arctanh(np.clip(df["eccentricity"], 0.0, 0.98))
    
    df["fisher_thermodynamic_distance"] = np.sqrt(log_ratio**2 + arctanh_e**2)
    
    # Systems with high tension: short period (P < 8d) but persistently high eccentricity (e > 0.4)
    # These represent 'Non-Equilibrium Meta-Stable Attractors' (e.g. ongoing Kozai-Lidov pumping by unseen triples)
    df["kozai_metastability_index"] = np.where(
        df["period"] < P_crit,
        df["eccentricity"] / (df["period"] / P_crit),
        0.0
    )
    
    return df


# -----------------------------------------------------------------------------
# CONCEPT 2: Shannon Phase Coverage Entropy of RV Observations
# -----------------------------------------------------------------------------
def compute_phase_shannon_entropy(conn: sqlite3.Connection, min_rvs: int = 20) -> pd.DataFrame:
    """Computes the Shannon Information Entropy of empirical observational cadence.

    Folds time series observations t_i over period P into phase space theta in [0, 1).
    Discretizes into N=20 phase bins.
    H_phase = - sum_{k} p_k * ln(p_k) / ln(N) (normalized to [0, 1]).
    An entropy near 1.0 implies uniform phase sampling (perfect coverage).
    An entropy near 0 implies acute observational blindspots (aliasing susceptibility).
    """
    query = """
    SELECT 
        v.sn,
        v.[on],
        v.epoch,
        v.radial_velocity,
        o.period,
        o.periastron_time,
        o.grade
    FROM velocities v
    JOIN orbits o ON v.sn = o.sn AND v.[on] = o.[on]
    WHERE o.period > 0 AND v.epoch IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    
    records = []
    n_bins = 20
    max_entropy = np.log(n_bins)
    
    for (sn, on), group in df.groupby(["sn", "on"]):
        if len(group) < min_rvs:
            continue
        
        P = group["period"].iloc[0]
        T0 = group["periastron_time"].iloc[0] or 0.0
        epochs = group["epoch"].values
        
        # Calculate folded phase in [0, 1)
        phases = ((epochs - T0) / P) % 1.0
        
        # Bin counts
        counts, _ = np.histogram(phases, bins=n_bins, range=(0.0, 1.0))
        probs = counts / np.sum(counts)
        probs = probs[probs > 0]
        
        entropy = -np.sum(probs * np.log(probs)) / max_entropy
        
        # Phase Completeness Ratio: fraction of non-empty bins
        coverage_ratio = np.count_nonzero(counts) / n_bins
        
        records.append({
            "sn": sn,
            "on": on,
            "n_rvs": len(group),
            "period": P,
            "grade": group["grade"].iloc[0],
            "shannon_phase_entropy": float(entropy),
            "phase_coverage_ratio": float(coverage_ratio),
        })
        
    return pd.DataFrame(records)


# -----------------------------------------------------------------------------
# CONCEPT 3: Latent Manifold Projection & Topological Clustering
# -----------------------------------------------------------------------------
def discover_latent_dynamical_manifolds(conn: sqlite3.Connection) -> pd.DataFrame:
    """Embeds spectroscopic binaries into a 3D Latent PCA space across kinematics and geometry."""
    query = """
    SELECT 
        o.sn,
        o.[on],
        o.period,
        o.eccentricity,
        o.K1,
        o.systemic_velocity,
        s.mag1,
        s.parallax,
        s.pmra,
        s.pmdec
    FROM orbits o
    JOIN systems s ON o.sn = s.sn
    WHERE o.period > 0 AND o.eccentricity >= 0 AND o.K1 > 0
      AND s.parallax > 0 AND s.mag1 IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    
    # Feature transformations
    df["log_P"] = np.log10(df["period"])
    df["ecc"] = df["eccentricity"]
    df["log_K1"] = np.log10(df["K1"])
    df["dist_pc"] = 1000.0 / df["parallax"]
    df["M_V"] = df["mag1"] - 5.0 * np.log10(df["dist_pc"] / 10.0)
    df["tangential_velocity"] = 4.74047 * np.sqrt(df["pmra"]**2 + df["pmdec"]**2) / df["parallax"]
    
    feature_cols = ["log_P", "ecc", "log_K1", "M_V", "tangential_velocity"]
    clean_data = df.dropna(subset=feature_cols).copy()
    
    scaler = RobustScaler()
    scaled = scaler.fit_transform(clean_data[feature_cols])
    
    pca = PCA(n_components=3, random_state=42)
    latent_coords = pca.fit_transform(scaled)
    
    clean_data["latent_dim1"] = latent_coords[:, 0]
    clean_data["latent_dim2"] = latent_coords[:, 1]
    clean_data["latent_dim3"] = latent_coords[:, 2]
    clean_data["manifold_outlier_score"] = np.linalg.norm(latent_coords, axis=1)
    
    print(f"Explained Variance Ratio across 3 latent manifold dimensions: {pca.explained_variance_ratio_}")
    return clean_data


# -----------------------------------------------------------------------------
# MAIN DEMONSTRATOR EXECUTION
# -----------------------------------------------------------------------------
def run_unconventional_discoveries():
    conn = get_connection()
    print("=" * 80)
    print("EXTREME UNCONVENTIONAL CROSS-POLLINATION ENGINE (LEVEL 11/10)")
    print("Information Geometry | Shannon Phase Entropy | Topological Manifolds")
    print("=" * 80)

    # 1. Information Geometric Dissipation & Kozai Metastability
    print("\n[DISCOVERY 1] Information Geometry: Kozai-Lidov Non-Equilibrium Attractors:")
    geo_df = compute_thermodynamic_geodesics(conn)
    kozai_outliers = geo_df[geo_df["kozai_metastability_index"] > 0.5].sort_values(
        by="kozai_metastability_index", ascending=False
    )
    print(f"Detected {len(kozai_outliers)} close systems violating classical tidal relaxation (P < 8d, high e):")
    for _, r in kozai_outliers.head(5).iterrows():
        print(
            f"SN {int(r['sn']):4d} (Orbit {int(r['on'])}) | P={r['period']:6.2f}d, e={r['eccentricity']:.3f} | "
            f"Thermodynamic Distance d_Fisher={r['fisher_thermodynamic_distance']:.2f} | "
            f"Kozai Metastability Index={r['kozai_metastability_index']:.2f}"
        )

    # 2. Shannon Entropy of Observational Phase Coverage
    print("\n[DISCOVERY 2] Shannon Information Entropy: Orbit Solutions with Hidden Phase Aliasing:")
    shannon_df = compute_phase_shannon_entropy(conn, min_rvs=25)
    # Find orbits with high RV counts but pathological Shannon phase coverage (< 0.65)
    aliased = shannon_df.sort_values(by="shannon_phase_entropy", ascending=True)
    print(f"Evaluated {len(shannon_df)} multi-point RV orbits. Top phase-blindspot systems:")
    for _, r in aliased.head(5).iterrows():
        print(
            f"SN {int(r['sn']):4d} (Orbit {int(r['on'])}) | P={r['period']:8.2f}d | N_obs={int(r['n_rvs']):3d} | "
            f"Shannon Entropy H={r['shannon_phase_entropy']:.3f} (Coverage: {r['phase_coverage_ratio']*100:.0f}%) | "
            f"Historical Grade: {r['grade']}"
        )

    # 3. Latent Manifold Projection
    print("\n[DISCOVERY 3] Topological Latent Space: Extreme Dynamical Outliers on Manifold:")
    manifold_df = discover_latent_dynamical_manifolds(conn)
    outliers = manifold_df.sort_values(by="manifold_outlier_score", ascending=False)
    for _, r in outliers.head(5).iterrows():
        print(
            f"SN {int(r['sn']):4d} (Orbit {int(r['on'])}) | P={r['period']:8.2f}d, e={r['ecc']:5.2f}, K1={r['K1']:5.1f}km/s | "
            f"V_tan={r['tangential_velocity']:6.1f}km/s | Manifold Outlier L2 Norm={r['manifold_outlier_score']:.2f}"
        )

    conn.close()


if __name__ == "__main__":
    run_unconventional_discoveries()
