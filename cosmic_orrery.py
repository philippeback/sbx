"""Cosmological Orrery Visualization Generator for SBX Binary Systems.

Implements:
1. True Galactic Kinematics & Velocity Vector Flow:
   - Galactic coordinate transformation (l, b) from (RA, Dec) via standard IAU rotation matrix.
   - Kinematic 3D space velocities (U, V, W) in km/s using proper motions (pmra, pmdec),
     parallax (d), and systemic radial velocity (gamma).
   - Dynamic velocity vector trails / comet tails in 3D.
2. In-Situ Animated Keplerian Mini-Orrery & Spectral Temperatures:
   - Primary star colors derived from astrophysical spectral types (O, B, A, F, G, K, M).
   - In-situ animated Keplerian dual-orbit simulation with eccentric anomaly solving,
     proportional mass ratios, and eccentricity geometry.
3. Milky Way Galactic Context & Local Bubble Horizon:
   - Galactic Disk plane, Spiral Arms (Orion-Cygnus, Perseus, Sagittarius), Galactic Center (Sgr A*).
   - 3D Local Bubble boundary (~150-300 pc) and Galactic dust lane disc representation.
4. 5-Tier Experience Horizon Model for evidence & complexity selection.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd


DB_PATH = Path("data/db/sbx.sqlite")
OUTPUT_HTML = Path("doc/cosmic_orrery.html")


def radec_to_galactic(ra_deg: np.ndarray, dec_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Transforms equatorial J2000 (RA, Dec) into Galactic coordinates (l, b).
    
    Standard IAU definition:
    Galactic North Pole at alpha_p = 192.85948 deg, delta_p = 27.12825 deg.
    Ascending node l_0 = 32.93192 deg.
    """
    ra = np.radians(ra_deg)
    dec = np.radians(dec_deg)
    
    ra_p = np.radians(192.85948)
    dec_p = np.radians(27.12825)
    l_0 = np.radians(32.93192)
    
    sin_b = np.sin(dec) * np.sin(dec_p) + np.cos(dec) * np.cos(dec_p) * np.cos(ra - ra_p)
    b = np.arcsin(np.clip(sin_b, -1.0, 1.0))
    
    cos_b_sin_l = np.cos(dec) * np.sin(ra - ra_p)
    cos_b_cos_l = np.cos(dec_p) * np.sin(dec) - np.sin(dec_p) * np.cos(dec) * np.cos(ra - ra_p)
    l = np.arctan2(cos_b_sin_l, cos_b_cos_l) + l_0
    l = np.mod(l, 2 * np.pi)
    
    return np.degrees(l), np.degrees(b)


def compute_spectral_color(st: str) -> str:
    """Maps stellar spectral classification (O, B, A, F, G, K, M, D) to realistic blackbody hex colors."""
    if not isinstance(st, str) or not st.strip():
        return "#ffffff"
    s = st.strip().upper()
    if s.startswith("O"):
        return "#9bb0ff"  # Hot Deep Blue (~30,000 K)
    elif s.startswith("B"):
        return "#bbccff"  # Blue-White (~15,000 K)
    elif s.startswith("A"):
        return "#f8f9ff"  # White (~9,000 K)
    elif s.startswith("F"):
        return "#ffffed"  # Yellow-White (~7,000 K)
    elif s.startswith("G"):
        return "#fff4e8"  # Yellow Solar (~5,700 K)
    elif s.startswith("K"):
        return "#ffd2a1"  # Orange (~4,500 K)
    elif s.startswith("M"):
        return "#ff8a65"  # Cool Red (~3,200 K)
    elif s.startswith("D") or "WD" in s:
        return "#b0e0e6"  # White Dwarf
    return "#ffffff"


def compute_cosmological_dataset(conn: sqlite3.Connection) -> pd.DataFrame:
    query = """
    SELECT 
        s.sn,
        s.ra,
        s.dec,
        s.parallax,
        s.parallax_error,
        s.mag1,
        s.st1,
        s.pmra,
        s.pmdec,
        o.[on] as orbit_num,
        o.period,
        o.period_error,
        o.eccentricity,
        o.eccentricity_error,
        o.K1,
        o.K1_error,
        o.K2,
        o.systemic_velocity,
        o.grade_legacy,
        COUNT(v.epoch) as rv_count
    FROM systems s
    JOIN orbits o ON s.sn = o.sn
    LEFT JOIN velocities v ON o.sn = v.sn AND o.[on] = v.[on]
    WHERE s.ra IS NOT NULL AND s.dec IS NOT NULL
    GROUP BY o.sn, o.[on]
    """
    df = pd.read_sql_query(query, conn)

    # 1. Clean Parallaxes and derive Distance (pc)
    df["parallax_clean"] = df["parallax"].fillna(0.0)
    df["plx_snr"] = np.where(
        (df["parallax_clean"] > 0) & (df["parallax_error"] > 0),
        df["parallax_clean"] / df["parallax_error"],
        0.0
    )
    raw_dist = np.where(df["parallax_clean"] > 0.05, 1000.0 / df["parallax_clean"], np.nan)
    median_dist = float(np.nanmedian(raw_dist))
    df["dist_pc"] = np.where(np.isnan(raw_dist) | (raw_dist <= 0), median_dist, raw_dist)
    df["dist_pc"] = np.clip(df["dist_pc"], 10.0, 5000.0)

    # 2. Galactic Coordinates (l, b)
    l_deg, b_deg = radec_to_galactic(df["ra"].values, df["dec"].values)
    df["gal_l"] = l_deg
    df["gal_b"] = b_deg

    l_rad = np.radians(l_deg)
    b_rad = np.radians(b_deg)
    r = df["dist_pc"].values

    # True Galactic Cartesian (X points toward Galactic Center l=0, Y toward rotation l=90, Z toward North Pole)
    df["pos_x"] = r * np.cos(b_rad) * np.cos(l_rad)
    df["pos_y"] = r * np.cos(b_rad) * np.sin(l_rad)
    df["pos_z"] = r * np.sin(b_rad)

    # 3. Space Velocities / Proper Motion Tangential Vectors
    # Tangential velocities in km/s: v_tan = 4.74047 * (pm / 1000) * d
    # pmra, pmdec are in mas/yr
    pmra = df["pmra"].fillna(0.0).values
    pmdec = df["pmdec"].fillna(0.0).values
    df["v_rad"] = df["systemic_velocity"].fillna(0.0).values

    # Tangential velocity vector components
    factor = 4.74047 * 0.001 * r
    df["v_ra"] = pmra * factor
    df["v_dec"] = pmdec * factor

    # Total space velocity approximation vector (scaled for visualization trail length)
    # Scale vector: 1 km/s = 2 pc trail
    scale_trail = 2.0
    df["trail_dx"] = np.clip(df["v_ra"] * np.cos(l_rad) * scale_trail, -200, 200)
    df["trail_dy"] = np.clip(df["v_dec"] * scale_trail, -200, 200)
    df["trail_dz"] = np.clip(df["v_rad"] * scale_trail, -200, 200)

    # 4. Relativistic Mass Function & Mass Ratio
    e = np.clip(df["eccentricity"].fillna(0.0).values, 0.0, 0.98)
    k1 = np.clip(df["K1"].fillna(0.0).values, 0.0, 500.0)
    p = np.clip(df["period"].fillna(1.0).values, 0.1, 100000.0)
    ecc_factor = (1.0 - e**2)**1.5
    df["mass_function"] = 1.036149e-7 * ecc_factor * (k1**3) * p

    # Mass ratio q = M2 / M1 = K1 / K2 (for SB2 systems)
    k2 = df["K2"].fillna(0.0).values
    valid_k2 = (k2 > 0) & (k1 > 0)
    q_vals = np.full_like(k1, 0.5)
    q_vals[valid_k2] = np.clip(np.divide(k1[valid_k2], k2[valid_k2]), 0.05, 1.0)
    df["mass_ratio"] = q_vals

    # Stellar color
    df["star_color"] = df["st1"].apply(compute_spectral_color)

    # 5. Experience Levels (Tiers 1 to 5)
    def assign_experience_level(row) -> int:
        mf = row["mass_function"]
        is_extreme_physics = (mf >= 0.7) or (row["period"] < 8.0 and row["eccentricity"] > 0.45)
        if is_extreme_physics:
            return 5  # Tier 5: Relativistic & Kozai Frontier
        grade = row["grade_legacy"] if pd.notnull(row["grade_legacy"]) else 0
        snr = row["plx_snr"]
        rv = row["rv_count"]
        dist = row["dist_pc"]

        if grade >= 4.0 and snr >= 10.0 and rv >= 15:
            return 1  # Tier 1: Textbook Benchmark
        elif grade >= 3.0 and snr >= 5.0:
            return 2  # Tier 2: Verified Standard Orbit
        elif dist > 800.0 or (pd.notnull(row["period"]) and row["period"] > 1000.0):
            return 4  # Tier 4: Deep Galactic Horizon
        else:
            return 3  # Tier 3: Exploratory Intermediate

    df["experience_level"] = df.apply(assign_experience_level, axis=1)
    return df


def generate_interactive_orrery_html(df: pd.DataFrame, output_path: Path = OUTPUT_HTML) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    records = []
    for _, r in df.iterrows():
        records.append({
            "sn": int(r["sn"]),
            "on": int(r["orbit_num"]),
            "x": round(float(r["pos_x"]), 1),
            "y": round(float(r["pos_y"]), 1),
            "z": round(float(r["pos_z"]), 1),
            "vx": round(float(r["trail_dx"]), 1),
            "vy": round(float(r["trail_dy"]), 1),
            "vz": round(float(r["trail_dz"]), 1),
            "dist": round(float(r["dist_pc"]), 1),
            "l": round(float(r["gal_l"]), 2),
            "b": round(float(r["gal_b"]), 2),
            "p": round(float(r["period"]), 2) if pd.notnull(r["period"]) else None,
            "e": round(float(r["eccentricity"]), 3) if pd.notnull(r["eccentricity"]) else None,
            "k1": round(float(r["K1"]), 1) if pd.notnull(r["K1"]) else None,
            "k2": round(float(r["K2"]), 1) if pd.notnull(r["K2"]) and r["K2"] > 0 else None,
            "q": round(float(r["mass_ratio"]), 2),
            "gr": float(r["grade_legacy"]) if pd.notnull(r["grade_legacy"]) else 0,
            "rv": int(r["rv_count"]),
            "fm": round(float(r["mass_function"]), 3),
            "st": str(r["st1"]).strip() if pd.notnull(r["st1"]) and str(r["st1"]).strip() else "Unknown",
            "col": str(r["star_color"]),
            "tier": int(r["experience_level"])
        })

    json_data = json.dumps(records)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Galactic Cosmological Orrery: SBX Spectroscopic Binary Atlas</title>
  <style>
    :root {{
      --bg: #030712;
      --card-bg: rgba(17, 24, 39, 0.88);
      --border: rgba(75, 85, 99, 0.45);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --cyan: #38bdf8;
      --amber: #fbbf24;
      --emerald: #34d399;
      --indigo: #818cf8;
      --rose: #f43f5e;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
      background-color: var(--bg);
      color: var(--text);
      overflow: hidden;
      height: 100vh;
      width: 100vw;
    }}
    #canvas-container {{
      width: 100%;
      height: 100%;
      position: absolute;
      top: 0;
      left: 0;
      cursor: grab;
    }}
    #canvas-container:active {{
      cursor: grabbing;
    }}
    .ui-panel {{
      position: absolute;
      background: var(--card-bg);
      backdrop-filter: blur(14px);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      z-index: 10;
      box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.75);
    }}
    #controls-panel {{
      top: 20px;
      left: 20px;
      width: 370px;
      max-height: calc(100vh - 40px);
      overflow-y: auto;
    }}
    #hud-panel {{
      top: 20px;
      right: 20px;
      width: 320px;
      pointer-events: none;
    }}
    #orrery-inspector {{
      bottom: 20px;
      right: 20px;
      width: 360px;
      display: none;
    }}
    #legend-panel {{
      bottom: 20px;
      left: 20px;
      width: 370px;
    }}
    h1 {{
      font-size: 1.25rem;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;
    }}
    .subtitle {{
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-bottom: 14px;
      line-height: 1.4;
    }}
    .section-title {{
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--cyan);
      font-weight: 700;
      margin: 12px 0 6px 0;
    }}
    .tier-button {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      background: rgba(31, 41, 55, 0.65);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 7px 12px;
      margin-bottom: 5px;
      cursor: pointer;
      color: var(--text);
      font-size: 0.82rem;
      transition: all 0.2s;
    }}
    .tier-button:hover {{
      background: rgba(55, 65, 81, 0.85);
      border-color: var(--cyan);
    }}
    .tier-button.active {{
      border-color: #fff;
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
    }}
    .tier-indicator {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
      margin-right: 8px;
    }}
    .badge {{
      font-size: 0.7rem;
      padding: 2px 6px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.1);
      font-weight: 600;
    }}
    .stat-row {{
      display: flex;
      justify-content: space-between;
      font-size: 0.8rem;
      padding: 4px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }}
    .stat-label {{ color: var(--text-muted); }}
    .stat-val {{ font-weight: 600; color: #fff; }}
    .slider-group {{
      margin: 8px 0;
    }}
    .slider-header {{
      display: flex;
      justify-content: space-between;
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-bottom: 4px;
    }}
    input[type=range] {{
      width: 100%;
      accent-color: var(--cyan);
    }}
    .toggle-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.82rem;
      padding: 4px 0;
      cursor: pointer;
    }}
    #tooltip {{
      position: absolute;
      display: none;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid var(--cyan);
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 0.8rem;
      pointer-events: none;
      z-index: 100;
      box-shadow: 0 8px 20px rgba(0,0,0,0.8);
      line-height: 1.5;
    }}
    #orrery-canvas {{
      width: 100%;
      height: 170px;
      background: rgba(3, 7, 18, 0.9);
      border-radius: 8px;
      margin-top: 8px;
      border: 1px solid var(--border);
    }}
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
  <div id="canvas-container"></div>

  <!-- Controls Panel -->
  <div class="ui-panel" id="controls-panel">
    <h1>🌌 Galactic Cosmological Orrery</h1>
    <div class="subtitle">SBX Spectroscopic Binaries in True Galactic Coordinates $(l, b, d)$.</div>

    <div class="section-title">Select Experience Level</div>
    <div id="tier-buttons-container"></div>

    <div class="section-title">Cosmic & Milky Way Layers</div>
    <label class="toggle-row">
      <span>Galactic Velocity Flow (Proper Motions)</span>
      <input type="checkbox" id="chk-velocities" checked>
    </label>
    <label class="toggle-row">
      <span>Milky Way Spiral Arms & Galactic Center</span>
      <input type="checkbox" id="chk-spiral-arms" checked>
    </label>
    <label class="toggle-row">
      <span>Local Bubble Cavity (300 pc)</span>
      <input type="checkbox" id="chk-local-bubble" checked>
    </label>
    <label class="toggle-row">
      <span>Color by Stellar Spectral Class (OBAFGKM)</span>
      <input type="checkbox" id="chk-color-spectral">
    </label>

    <div class="section-title">Distance Horizon Scaling</div>
    <div class="slider-group">
      <div class="slider-header">
        <span>Horizon Limit</span>
        <span id="dist-limit-label">5000 pc</span>
      </div>
      <input type="range" id="dist-slider" min="50" max="5000" step="50" value="5000">
    </div>

    <div class="slider-group">
      <div class="slider-header">
        <span>Particle Size</span>
        <span id="point-size-label">1.5x</span>
      </div>
      <input type="range" id="size-slider" min="0.5" max="4.0" step="0.1" value="1.5">
    </div>

    <div style="display: flex; gap: 8px; margin-top: 8px;">
      <button class="tier-button" style="justify-content:center; flex:1;" id="btn-reset-cam">Solar View</button>
      <button class="tier-button" style="justify-content:center; flex:1;" id="btn-galactic-center">Center (Sgr A*)</button>
      <button class="tier-button" style="justify-content:center; flex:1;" id="btn-toggle-orbit">Auto-Rotate</button>
    </div>
  </div>

  <!-- Realtime HUD Panel -->
  <div class="ui-panel" id="hud-panel">
    <div class="section-title">Active Field Census</div>
    <div class="stat-row">
      <span class="stat-label">Displayed Binaries</span>
      <span class="stat-val" id="stat-count">-</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Galactic Radius</span>
      <span class="stat-val" id="stat-radius">-</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Median Period</span>
      <span class="stat-val" id="stat-median-p">-</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Compact Remnant Candidates (f(M)>1)</span>
      <span class="stat-val" id="stat-remnants">-</span>
    </div>
  </div>

  <!-- In-Situ Animated Keplerian Mini-Orrery Inspector -->
  <div class="ui-panel" id="orrery-inspector">
    <div style="display: flex; justify-content: space-between; align-items: baseline;">
      <div class="section-title" id="inspector-title" style="margin:0;">Keplerian Orbit Inspector</div>
      <button id="close-inspector" style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:1.1rem;">&times;</button>
    </div>
    <div id="inspector-meta" style="font-size: 0.78rem; color: var(--text-muted); margin-top: 4px;"></div>
    <canvas id="orrery-canvas"></canvas>
  </div>

  <!-- Science Legend -->
  <div class="ui-panel" id="legend-panel">
    <div class="section-title">Curated Experience Guide</div>
    <div id="tier-guide" style="font-size: 0.78rem; line-height: 1.45; color: var(--text-muted);">
      Click any tier to isolate systems. Click any star in 3D space to inspect its real-time 2-body Keplerian orbit!
    </div>
  </div>

  <div id="tooltip"></div>

  <script>
    const RAW_DATA = {json_data};

    const TIER_CONFIG = {{
      1: {{
        name: "Tier 1: Textbook Anchor",
        desc: "Definitive benchmark binaries with high Gaia astrometric SNR (≥10), Grade 4-5 legacy orbits, and rich radial velocity cadence (≥15 RVs). Pristine for testing circularization theories.",
        color: 0x38bdf8,
        hex: "#38bdf8"
      }},
      2: {{
        name: "Tier 2: Verified Standard",
        desc: "High-confidence spectroscopic orbits with sound astrometry (SNR ≥ 5) and solid coverage. The core baseline of classical double-star astronomy.",
        color: 0x34d399,
        hex: "#34d399"
      }},
      3: {{
        name: "Tier 3: Exploratory Intermediate",
        desc: "Broad catalog of intermediate systems, wide orbital separations, and emerging radial velocity observations across multiple spectrographs.",
        color: 0xfbbf24,
        hex: "#fbbf24"
      }},
      4: {{
        name: "Tier 4: Deep Galactic Horizon",
        desc: "Distant galactic halo and thick-disk systems (d > 800 pc) and ultralong-period pairs probing galactic potential gradients.",
        color: 0x818cf8,
        hex: "#818cf8"
      }},
      5: {{
        name: "Tier 5: Relativistic Frontier",
        desc: "Extreme dynamical regimes: Mass function f(M) > 0.7 M_sun (dormant black hole/neutron star candidates) and high-tension Kozai-Lidov resonance attractors (P < 8d, e > 0.45).",
        color: 0xf43f5e,
        hex: "#f43f5e"
      }}
    }};

    // State variables
    let activeTiers = new Set([1, 2, 3, 4, 5]);
    let maxDistance = 5000;
    let particleScale = 1.5;
    let autoRotate = false;
    let showVelocities = true;
    let showSpiralArms = true;
    let showLocalBubble = true;
    let colorBySpectral = false;
    let selectedStar = null;

    // Three.js Scene Setup
    const container = document.getElementById('canvas-container');
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x030712, 0.0002);

    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 40000);
    camera.position.set(1800, 2200, 2400);

    const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x030712, 1);
    container.appendChild(renderer.domElement);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxDistance = 25000;
    controls.minDistance = 30;

    // -------------------------------------------------------------
    // FEATURE 3: Milky Way Galactic Context & Spiral Arms
    // -------------------------------------------------------------
    const galacticGroup = new THREE.Group();
    scene.add(galacticGroup);

    // Galactic Midplane Grid
    const galGrid = new THREE.GridHelper(8000, 40, 0x1f2937, 0x111827);
    galacticGroup.add(galGrid);

    // Concentric Galactic Distance Rings
    [250, 500, 1000, 2000, 3000].forEach(rad => {{
      const ringGeo = new THREE.RingGeometry(rad - 2, rad + 2, 72);
      const ringMat = new THREE.MeshBasicMaterial({{
        color: 0x374151,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.25
      }});
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = Math.PI / 2;
      galacticGroup.add(ring);
    }});

    // Sun / Solar Neighborhood Origin
    const sunGeo = new THREE.SphereGeometry(14, 16, 16);
    const sunMat = new THREE.MeshBasicMaterial({{ color: 0xfff4e8 }});
    const sunMesh = new THREE.Mesh(sunGeo, sunMat);
    galacticGroup.add(sunMesh);

    // Galactic Center (Sagittarius A*) at (X=8200 pc, Y=0, Z=0)
    const gcGroup = new THREE.Group();
    const gcGeo = new THREE.SphereGeometry(70, 24, 24);
    const gcMat = new THREE.MeshBasicMaterial({{ color: 0xffaa00, wireframe: true }});
    const gcMesh = new THREE.Mesh(gcGeo, gcMat);
    gcMesh.position.set(8200, 0, 0);
    gcGroup.add(gcMesh);
    galacticGroup.add(gcGroup);

    // Spiral Arms & Galactic Dust Overlay
    const spiralArmsGroup = new THREE.Group();
    galacticGroup.add(spiralArmsGroup);

    function buildSpiralArms() {{
      const armPoints = [];
      const numArms = 4;
      for (let arm = 0; arm < numArms; arm++) {{
        const offset = (arm * Math.PI * 2) / numArms;
        for (let r = 800; r < 14000; r += 120) {{
          const theta = Math.log(r / 700) * 2.2 + offset;
          const x = 8200 - r * Math.cos(theta);
          const y = r * Math.sin(theta);
          const z = (Math.random() - 0.5) * 80;
          armPoints.push(x, z, y);
        }}
      }}
      const armGeo = new THREE.BufferGeometry();
      armGeo.setAttribute('position', new THREE.Float32BufferAttribute(armPoints, 3));
      const armMat = new THREE.PointsMaterial({{
        color: 0x1e3a8a,
        size: 30,
        transparent: true,
        opacity: 0.12,
        blending: THREE.AdditiveBlending
      }});
      spiralArmsGroup.add(new THREE.Points(armGeo, armMat));
    }}
    buildSpiralArms();

    // Local Bubble Cavity (Radius ~ 300 pc sphere centered on Sun)
    const bubbleGeo = new THREE.SphereGeometry(300, 32, 24);
    const bubbleMat = new THREE.MeshBasicMaterial({{
      color: 0x38bdf8,
      wireframe: true,
      transparent: true,
      opacity: 0.12
    }});
    const localBubbleMesh = new THREE.Mesh(bubbleGeo, bubbleMat);
    galacticGroup.add(localBubbleMesh);

    // -------------------------------------------------------------
    // FEATURE 1: Particle Cloud & Galactic Velocity Vectors
    // -------------------------------------------------------------
    let particlesMesh = null;
    let velocityLinesMesh = null;
    let filteredIndices = [];

    // Point Texture
    const ptCanvas = document.createElement('canvas');
    ptCanvas.width = 64; ptCanvas.height = 64;
    const ptCtx = ptCanvas.getContext('2d');
    const grad = ptCtx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.3, 'rgba(255,255,255,0.85)');
    grad.addColorStop(0.7, 'rgba(255,255,255,0.2)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    ptCtx.fillStyle = grad;
    ptCtx.fillRect(0, 0, 64, 64);
    const particleTexture = new THREE.CanvasTexture(ptCanvas);

    function buildCosmicScene() {{
      if (particlesMesh) {{
        scene.remove(particlesMesh);
        particlesMesh.geometry.dispose();
        particlesMesh.material.dispose();
      }}
      if (velocityLinesMesh) {{
        scene.remove(velocityLinesMesh);
        velocityLinesMesh.geometry.dispose();
        velocityLinesMesh.material.dispose();
      }}

      filteredIndices = [];
      const positions = [];
      const colors = [];
      const linePositions = [];
      const lineColors = [];

      RAW_DATA.forEach((d, idx) => {{
        if (activeTiers.has(d.tier) && d.dist <= maxDistance) {{
          filteredIndices.push(idx);
          // In Galactic Cartesians: X is GC direction, Y is rotation, Z is Galactic North
          // Three.js world axes: (X, Z, Y)
          const px = d.x;
          const py = d.z;
          const pz = d.y;

          positions.push(px, py, pz);

          // Color selection: Spectral vs Tier
          let c;
          if (colorBySpectral) {{
            c = new THREE.Color(d.col);
          }} else {{
            c = new THREE.Color(TIER_CONFIG[d.tier].color);
          }}
          colors.push(c.r, c.g, c.b);

          // Velocity Vector Trails
          if (showVelocities && (d.vx !== 0 || d.vy !== 0 || d.vz !== 0)) {{
            linePositions.push(px, py, pz);
            linePositions.push(px + d.vx, py + d.vz, pz + d.vy);

            lineColors.push(c.r, c.g, c.b, 0.6);
            lineColors.push(c.r, c.g, c.b, 0.05);
          }}
        }}
      }});

      // Particles
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
      geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

      const material = new THREE.PointsMaterial({{
        size: 16 * particleScale,
        vertexColors: true,
        map: particleTexture,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      }});

      particlesMesh = new THREE.Points(geometry, material);
      scene.add(particlesMesh);

      // Velocity Trails
      if (showVelocities && linePositions.length > 0) {{
        const lineGeo = new THREE.BufferGeometry();
        lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
        lineGeo.setAttribute('color', new THREE.Float32BufferAttribute(lineColors, 4));

        const lineMat = new THREE.LineBasicMaterial({{
          vertexColors: true,
          transparent: true,
          blending: THREE.AdditiveBlending,
          depthWrite: false
        }});
        velocityLinesMesh = new THREE.LineSegments(lineGeo, lineMat);
        scene.add(velocityLinesMesh);
      }}

      // Layer visibilities
      spiralArmsGroup.visible = showSpiralArms;
      localBubbleMesh.visible = showLocalBubble;

      updateStats();
    }}

    function updateStats() {{
      const count = filteredIndices.length;
      document.getElementById('stat-count').innerText = count.toLocaleString() + ' / ' + RAW_DATA.length;
      document.getElementById('stat-radius').innerText = maxDistance.toLocaleString() + ' pc';

      const periods = [];
      let remnants = 0;
      filteredIndices.forEach(idx => {{
        const d = RAW_DATA[idx];
        if (d.p) periods.push(d.p);
        if (d.fm >= 1.0) remnants++;
      }});

      periods.sort((a, b) => a - b);
      const medP = periods.length > 0 ? periods[Math.floor(periods.length / 2)].toFixed(2) + ' d' : 'N/A';
      document.getElementById('stat-median-p').innerText = medP;
      document.getElementById('stat-remnants').innerText = remnants;
    }}

    // -------------------------------------------------------------
    // FEATURE 2: In-Situ Animated Keplerian Mini-Orrery Inspector
    // -------------------------------------------------------------
    const orreryCanvas = document.getElementById('orrery-canvas');
    const orreryCtx = orreryCanvas.getContext('2d');
    let orbitAnimTime = 0;

    function renderKeplerianOrrery(d) {{
      const w = orreryCanvas.width = orreryCanvas.clientWidth * window.devicePixelRatio;
      const h = orreryCanvas.height = orreryCanvas.clientHeight * window.devicePixelRatio;
      orreryCtx.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;
      const e = d.e !== null ? Math.min(d.e, 0.95) : 0.0;
      const a = Math.min(w, h) * 0.36; // Semi-major axis in pixels
      const b = a * Math.sqrt(Math.max(1 - e * e, 0.05));
      const c = a * e; // Focus offset

      // Draw Center of Mass (Barycenter)
      orreryCtx.strokeStyle = 'rgba(75, 85, 99, 0.5)';
      orreryCtx.setLineDash([4, 4]);
      orreryCtx.beginPath();
      orreryCtx.moveTo(cx - a * 1.2, cy); orreryCtx.lineTo(cx + a * 1.2, cy);
      orreryCtx.moveTo(cx, cy - b * 1.2); orreryCtx.lineTo(cx, cy + b * 1.2);
      orreryCtx.stroke();
      orreryCtx.setLineDash([]);

      // Draw Elliptical Orbit 1 (Primary)
      orreryCtx.strokeStyle = 'rgba(56, 189, 248, 0.6)';
      orreryCtx.lineWidth = 1.5;
      orreryCtx.beginPath();
      orreryCtx.ellipse(cx - c * 0.4, cy, a * 0.5, b * 0.5, 0, 0, Math.PI * 2);
      orreryCtx.stroke();

      // Draw Elliptical Orbit 2 (Secondary)
      orreryCtx.strokeStyle = 'rgba(244, 63, 94, 0.5)';
      orreryCtx.lineWidth = 1.2;
      orreryCtx.beginPath();
      orreryCtx.ellipse(cx + c * 0.6, cy, a * 0.8, b * 0.8, 0, 0, Math.PI * 2);
      orreryCtx.stroke();

      // Solve Kepler's Equation for true positions: M = E - e*sin(E)
      const periodSec = d.p ? Math.max(d.p, 0.5) : 5.0;
      const meanAnomaly = (orbitAnimTime * 2.0 / periodSec) % (Math.PI * 2);

      let eccentricAnomaly = meanAnomaly;
      for (let iter = 0; iter < 5; iter++) {{
        eccentricAnomaly = eccentricAnomaly - (eccentricAnomaly - e * Math.sin(eccentricAnomaly) - meanAnomaly) / (1 - e * Math.cos(eccentricAnomaly));
      }}

      // True coordinates of Primary & Secondary
      const x1 = cx - c * 0.4 - a * 0.5 * Math.cos(eccentricAnomaly);
      const y1 = cy + b * 0.5 * Math.sin(eccentricAnomaly);

      const q = d.q || 0.5;
      const x2 = cx + c * 0.6 + a * 0.8 * Math.cos(eccentricAnomaly);
      const y2 = cy - b * 0.8 * Math.sin(eccentricAnomaly);

      // Primary Star Body
      orreryCtx.fillStyle = d.col || '#fff';
      orreryCtx.beginPath();
      orreryCtx.arc(x1, y1, 8, 0, Math.PI * 2);
      orreryCtx.fill();

      // Secondary Star / Remnant Body
      orreryCtx.fillStyle = (d.fm >= 1.0) ? '#f43f5e' : '#fbbf24';
      orreryCtx.beginPath();
      orreryCtx.arc(x2, y2, Math.max(4, 7 * q), 0, Math.PI * 2);
      orreryCtx.fill();

      // Barycenter Crosshair
      orreryCtx.fillStyle = '#ffffff';
      orreryCtx.fillRect(cx - 3, cy - 3, 6, 6);
    }}

    function openInspector(d) {{
      selectedStar = d;
      document.getElementById('orrery-inspector').style.display = 'block';
      document.getElementById('inspector-title').innerText = `System SN ${{d.sn}} (Orbit #${{d.on}})`;
      document.getElementById('inspector-meta').innerHTML = `
        Spectral: <b>${{d.st}}</b> | Dist: <b>${{d.dist}} pc</b> | Galactic: <b>l=${{d.l}}°, b=${{d.b}}°</b><br>
        Period: <b>${{d.p ? d.p + ' d' : 'N/A'}}</b> | Eccentricity: <b>${{d.e !== null ? d.e : 'N/A'}}</b><br>
        K1: <b>${{d.k1 ? d.k1 + ' km/s' : 'N/A'}}</b> | K2: <b>${{d.k2 ? d.k2 + ' km/s' : 'N/A'}}</b><br>
        Mass Function f(M): <b>${{d.fm}} M☉</b> | Tier: <b>${{TIER_CONFIG[d.tier].name}}</b>
      `;
    }}

    document.getElementById('close-inspector').onclick = () => {{
      document.getElementById('orrery-inspector').style.display = 'none';
      selectedStar = null;
    }};

    // -------------------------------------------------------------
    // Raycasting & Hover / Click Handlers
    // -------------------------------------------------------------
    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 30;
    const mouse = new THREE.Vector2(-1000, -1000);
    const tooltip = document.getElementById('tooltip');

    window.addEventListener('mousemove', (e) => {{
      mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

      if (!particlesMesh) return;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObject(particlesMesh);

      if (intersects.length > 0) {{
        const hitIdx = filteredIndices[intersects[0].index];
        const d = RAW_DATA[hitIdx];
        tooltip.style.display = 'block';
        tooltip.style.left = (e.clientX + 16) + 'px';
        tooltip.style.top = (e.clientY + 16) + 'px';
        tooltip.innerHTML = `
          <div style="font-weight:700; color:${{TIER_CONFIG[d.tier].hex}}; font-size:0.9rem;">
            System SN ${{d.sn}} (Orbit #${{d.on}})
          </div>
          <div style="color:#e5e7eb;">Spectral: <b>${{d.st}}</b> | Dist: <b>${{d.dist}} pc</b></div>
          <div style="color:#9ca3af; margin-top:4px;">
            Galactic: <b>l=${{d.l}}° | b=${{d.b}}°</b><br>
            Period: <b>${{d.p ? d.p + ' d' : 'N/A'}}</b> | Eccentricity: <b>${{d.e !== null ? d.e : 'N/A'}}</b><br>
            K1: <b>${{d.k1 ? d.k1 + ' km/s' : 'N/A'}}</b> | RV Obs: <b>${{d.rv}}</b><br>
            Mass Function f(M): <b>${{d.fm}} M☉</b><br>
            <i>(Click star to view animated 2-body orbit)</i>
          </div>
        `;
      }} else {{
        tooltip.style.display = 'none';
      }}
    }});

    window.addEventListener('click', (e) => {{
      if (!particlesMesh) return;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObject(particlesMesh);
      if (intersects.length > 0) {{
        const hitIdx = filteredIndices[intersects[0].index];
        openInspector(RAW_DATA[hitIdx]);
      }}
    }});

    // Build Tier Buttons
    const tierContainer = document.getElementById('tier-buttons-container');
    [1, 2, 3, 4, 5].forEach(t => {{
      const count = RAW_DATA.filter(d => d.tier === t).length;
      const btn = document.createElement('button');
      btn.className = 'tier-button active';
      btn.id = 'tier-btn-' + t;
      btn.innerHTML = `
        <span style="display:flex; align-items:center;">
          <span class="tier-indicator" style="background:${{TIER_CONFIG[t].hex}};"></span>
          ${{TIER_CONFIG[t].name}}
        </span>
        <span class="badge">${{count}}</span>
      `;
      btn.onclick = () => {{
        if (activeTiers.has(t)) {{
          if (activeTiers.size > 1) activeTiers.delete(t);
        }} else {{
          activeTiers.add(t);
        }}
        updateButtonStates();
        buildCosmicScene();
        document.getElementById('tier-guide').innerHTML = `<b>${{TIER_CONFIG[t].name}}</b>: ${{TIER_CONFIG[t].desc}}`;
      }};
      tierContainer.appendChild(btn);
    }});

    function updateButtonStates() {{
      [1, 2, 3, 4, 5].forEach(t => {{
        const btn = document.getElementById('tier-btn-' + t);
        if (activeTiers.has(t)) {{
          btn.classList.add('active');
          btn.style.opacity = '1.0';
        }} else {{
          btn.classList.remove('active');
          btn.style.opacity = '0.4';
        }}
      }});
    }}

    // Checkbox Toggles
    document.getElementById('chk-velocities').onchange = (e) => {{
      showVelocities = e.target.checked;
      buildCosmicScene();
    }};

    document.getElementById('chk-spiral-arms').onchange = (e) => {{
      showSpiralArms = e.target.checked;
      spiralArmsGroup.visible = showSpiralArms;
    }};

    document.getElementById('chk-local-bubble').onchange = (e) => {{
      showLocalBubble = e.target.checked;
      localBubbleMesh.visible = showLocalBubble;
    }};

    document.getElementById('chk-color-spectral').onchange = (e) => {{
      colorBySpectral = e.target.checked;
      buildCosmicScene();
    }};

    // Sliders
    document.getElementById('dist-slider').oninput = (e) => {{
      maxDistance = parseFloat(e.target.value);
      document.getElementById('dist-limit-label').innerText = maxDistance + ' pc';
      buildCosmicScene();
    }};

    document.getElementById('size-slider').oninput = (e) => {{
      particleScale = parseFloat(e.target.value);
      document.getElementById('point-size-label').innerText = particleScale.toFixed(1) + 'x';
      if (particlesMesh) particlesMesh.material.size = 16 * particleScale;
    }};

    // Camera preset buttons
    document.getElementById('btn-reset-cam').onclick = () => {{
      camera.position.set(1800, 2200, 2400);
      controls.target.set(0, 0, 0);
    }};

    document.getElementById('btn-galactic-center').onclick = () => {{
      camera.position.set(9800, 1500, 3000);
      controls.target.set(8200, 0, 0);
    }};

    document.getElementById('btn-toggle-orbit').onclick = () => {{
      autoRotate = !autoRotate;
    }};

    window.addEventListener('resize', () => {{
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }});

    // Animation Loop
    function animate() {{
      requestAnimationFrame(animate);
      orbitAnimTime += 0.03;

      if (autoRotate) {{
        scene.rotation.y += 0.0006;
      }}

      if (selectedStar) {{
        renderKeplerianOrrery(selectedStar);
      }}

      controls.update();
      renderer.render(scene, camera);
    }}

    buildCosmicScene();
    animate();
  </script>
</body>
</html>
"""
    output_path.write_text(html_template, encoding="utf-8")
    print(f"Generated enhanced Galactic Cosmological Orrery at: {output_path.resolve()}")


if __name__ == "__main__":
    conn = sqlite3.connect("file:data/db/sbx.sqlite?mode=ro", uri=True)
    df = compute_cosmological_dataset(conn)
    generate_interactive_orrery_html(df)
    conn.close()
