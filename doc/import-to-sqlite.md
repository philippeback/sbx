# System Architecture: Parquet to SQLite Ingestion Engine (`doc/import-to-sqlite.md`)

## 1. System Intent & Deterministic Boundaries

The objective of this subsystem is the deterministic, repeatable, and zero-data-loss ingestion of columnar Parquet snapshots into an embedded, high-throughput relational store (`data/db/sbx.sqlite`).

```text
[Upstream IVOA TAP Service]
            │
            ▼ (extract_sbx.py)
   [sbx_dump/*.parquet]  ──────── (Columnar Staging Area)
            │
            ▼ (load_to_sqlite.py)
  [data/db/sbx.sqlite]   ──────── (WAL-Optimized Relational State)
```

---

## 2. Ingestion Topology & Data Flow

### 2.1 Schema & Ingestion Order
Tables are ingested in topological dependency order to respect relational hierarchy:
1. `systems` (Parent entities: coordinates, components, magnitudes) — 4,080 records.
2. `orbits` (Orbital elements and solutions tied to systems) — 5,169 records.
3. `velocities` (High-cardinality radial velocity time-series observations) — 224,148 records.
4. `alias` (Identifier cross-references across catalogs) — 102,459 records.
5. `configurations` (Multi-body hierarchy topology) — 261 records.
6. `duplicates` (Cross-matched duplicate system records) — 18 records.

**Total Volume**: 336,135 relational rows consolidated into ~15.9 MB uncompressed SQLite footprint.

---

## 3. High-Performance SQLite Configuration (PRAGMA Matrix)

To eliminate write lock starvation, avoid lock escalations, and maximize multi-threaded read concurrency, the following SQLite engine parameters are systematically applied upon connection initialization:

| PRAGMA | Configured Value | Engineering Rationale |
| :--- | :--- | :--- |
| `journal_mode` | `WAL` | **Write-Ahead Logging**: Decouples readers from writers. Readers never block writers; writers never block readers. WAL creates persistent `-wal` and `-shm` sidecars. |
| `synchronous` | `NORMAL` | In WAL mode, `NORMAL` guarantees data integrity across application crashes while eliminating synchronous disk flushes per transaction. |
| `busy_timeout` | `5000` ms | Mitigates transient `SQLITE_BUSY` errors during concurrent access windows by configuring the engine to poll for up to 5 seconds before failing. |
| `cache_size` | `-64000` (64 MiB) | Sets working memory page cache to 64 megabytes (negative value denotes kibibytes), minimizing disk I/O churn during queries. |
| `foreign_keys` | `ON` | Enforces referential integrity at the database engine boundary. |
| `optimize` | `PRAGMA optimize;` | Runs internal query planner statistics optimization at the conclusion of bulk data load. |

---

## 4. Pipeline Execution Protocol

### Step 1: Environment Readiness
Ensure project virtual environment is synced:
```powershell
uv sync
```

### Step 2: Trigger Deterministic Loader
```powershell
uv run python load_to_sqlite.py
```

### Step 3: Execution Artifacts
Upon successful run, the file system contains:
- `data/db/sbx.sqlite`: Main database file.
- `data/db/sbx.sqlite-wal`: Write-Ahead Log (reabsorbed during checkpointing).
- `data/db/sbx.sqlite-shm`: Shared-memory index for concurrent WAL reads.

---

## 5. Verification & Consistency Auditing

Validation is verified directly via Python or the SQLite CLI:

```python
import sqlite3

conn = sqlite3.connect("data/db/sbx.sqlite")

# Verify Engine State
journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
assert journal_mode == "wal", f"Engine failed to maintain WAL mode: {journal_mode}"

# Audit Record Counts
EXPECTED_COUNTS = {
    "systems": 4080,
    "orbits": 5169,
    "velocities": 224148,
    "alias": 102459,
    "configurations": 261,
    "duplicates": 18,
}

for table, expected in EXPECTED_COUNTS.items():
    actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    assert actual == expected, f"Discrepancy in table {table}: expected {expected}, found {actual}"
    print(f"Verified {table}: {actual} rows.")
```

---

## 6. Failure Modes & Containment Strategies

1. **Schema Mismatch / Incomplete Upstream Pull**:
   - The script performs atomic table replacements (`if_exists="replace"`) to prevent dirty partial append states.
2. **CP1252 / Windows Output Encoding**:
   - All pipeline terminal reporting uses pure ASCII indicators (`[OK]`) rather than unicode emojis to prevent Windows console codec termination.
3. **Storage Boundary Isolation**:
   - The database and its WAL temporary artifacts are fully ignored in `.gitignore` (`data/`, `*.sqlite`, `*.sqlite-wal`, `*.sqlite-shm`) to prevent binary database pollution in the Git revision tree.
