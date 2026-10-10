# SBX TAP Data Extractor

A fast, lightweight extractor to dump all relational tables from the [SBX (Spectroscopic Binaries database)](https://www.astro.ulb.ac.be/sbx/tap_info/) TAP (Table Access Protocol) service using IVOA standards and `pyvo`.

The output is exported to column-optimized Apache Parquet files (and optionally CSV).

---

## 🌌 Interactive 3D Galactic Orrery

Explore the entire spectroscopic binary catalogue in an interactive 3D WebGL Galactic Orrery with true space kinematics, in-situ animated 2-body Keplerian orbits, and 5 curated experience tiers:

👉 **Live Interactive Visualizer: [https://philippeback.github.io/sbx/](https://philippeback.github.io/sbx/)**

- Full methodology and physics: [`doc/visualization.md`](doc/visualization.md)
- Generator script: [`cosmic_orrery.py`](cosmic_orrery.py)

---

## Tables Extracted

| Table | Description |
| :--- | :--- |
| `systems` | Central catalogue table (positions, proper motions, parallaxes, magnitudes) |
| `orbits` | Spectroscopic orbit parameters (periods, eccentricities, amplitudes $K_1, K_2$) |
| `velocities` | Individual radial velocity observations |
| `alias` | Cross-identifications across external catalogues (Gaia, Hipparcos, etc.) |
| `configurations`| Hierarchy mapping for multiple systems (triples, quadruples) |
| `duplicates` | Legacy duplicate resolution mappings from SB9 |

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (recommended) or Python $\ge$ 3.11

---

## Quick Start

### 1. Clone & Set Up

```bash
git clone <your-repo-url>
cd sbx-extractor
```

Sync environment and dependencies:
```bash
uv sync
```

### 2. Run Extraction

Execute the extractor script:
```bash
uv run python extract_sbx.py
```

All extracted tables will be saved into the `./sbx_dump/` directory as `.parquet` files.

---

## One-liner (No Clone / Ad-hoc)

You can run the script directly using `uv` ephemeral environments without creating a virtual environment manually:

```bash
uv run --with pyvo --with pandas --with pyarrow python extract_sbx.py
```

---

## Alternative: Direct cURL Download

If you need a specific table without installing Python:

```bash
curl -X POST "http://astro.ulb.ac.be/sbx/tap/sync" \
     -d "REQUEST=doQuery" \
     -d "LANG=ADQL" \
     -d "FORMAT=csv" \
     --data-urlencode "QUERY=SELECT * FROM systems" \
     -o systems.csv
```

---

## References

- [SBX TAP Service Info](https://www.astro.ulb.ac.be/sbx/tap_info/)
- [IVOA Table Access Protocol (TAP) Specification](http://www.ivoa.net/documents/TAP/)
- [PyVO Documentation](https://pyvo.readthedocs.io/)