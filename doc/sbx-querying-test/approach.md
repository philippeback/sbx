# Hyper-Systemized Testing Framework for SBX Relational Store (`doc/sbx-querying-test/approach.md`)

## 1. System Philosophy: Axiomatic Verification

To an **extreme hyper-systemizer**, a relational database is not merely a collection of tables; it is a **formal axiomatic system** where every row, column, relation, and query represents an invariant state.

Testing the SBX database (`data/db/sbx.sqlite`) cannot rely on arbitrary sample checks. Instead, we establish a **6-Layer Invariant Hierarchy** that systematically exercises the database from bare storage primitives up to complex astrophysical semantics:

```
┌────────────────────────────────────────────────────────┐
│  Layer 6: Multi-Body Graph Traversal & Topology        │  (Configurations)
├────────────────────────────────────────────────────────┤
│  Layer 5: Astrophysical Domain Semantics               │  (Physical laws & bounds)
├────────────────────────────────────────────────────────┤
│  Layer 4: Cross-Catalog Resolution Topology            │  (Equivalence classes)
├────────────────────────────────────────────────────────┤
│  Layer 3: Relational Integrity & Zero Orphanage        │  (Referential bounds)
├────────────────────────────────────────────────────────┤
│  Layer 2: Lossless Cardinality Invariants             │  (Completeness proofs)
├────────────────────────────────────────────────────────┤
│  Layer 1: Engine Primitives & Concurrency Modes (WAL) │  (SQLite PRAGMAs)
└────────────────────────────────────────────────────────┘
```

---

## 2. The 6-Layer Test Taxonomy

### Layer 1: Engine Invariants (`TestEnginePragmas`)
- **Axiom**: The database engine must enforce non-blocking concurrent reads and write-ahead persistence.
- **Assertions**:
  - `PRAGMA journal_mode` equals `WAL`.
  - All 6 target tables exist in `sqlite_master` with exact naming conventions.

### Layer 2: Lossless Cardinality Invariants (`TestCardinalityInvariants`)
- **Axiom**: Ingestion from columnar Parquet snapshots into SQLite must preserve record counts with 100% fidelity.
- **Target Invariant Matrix**:
  | Entity Table | Exact Expected Rows | Tolerable Delta |
  | :--- | :--- | :--- |
  | `systems` | **4,080** | **0** |
  | `orbits` | **5,169** | **0** |
  | `velocities` | **224,148** | **0** |
  | `alias` | **102,459** | **0** |
  | `configurations` | **261** | **0** |
  | `duplicates` | **18** | **0** |

### Layer 3: Relational Integrity & Zero Orphanage (`TestReferentialIntegrity`)
- **Axiom**: Every child entity in the graph must have an unambiguous parent entity (`sn`). Orphaned records represent database corruption.
- **Target Bounds**:
  - `orbits.sn ∉ systems.sn` $\equiv \emptyset$ (count = 0).
  - `velocities.sn ∉ systems.sn` $\equiv \emptyset$ (count = 0).
  - `alias.sn ∉ systems.sn` $\equiv \emptyset$ (count = 0).
  - `duplicates.(sn, sn_duplicate) ∉ systems.sn` $\equiv \emptyset$ (count = 0).

### Layer 4: Cross-Catalog Resolution Topology (`TestIdentifierResolution`)
- **Axiom**: Astronomical cross-matching requires that an external catalog identifier (e.g., Hipparcos, Gaia, 2MASS) correctly resolves to a single unified `sn` and its corresponding orbital solutions.
- **Target Behaviors**:
  - 1:N cardinality between `systems` and `orbits` is actively exercised (verifying multiple orbital solutions per single star).
  - Identifier resolution through `alias` $\rightarrow$ `systems` $\rightarrow$ `orbits` produces valid astronomical joins.

### Layer 5: Astrophysical Domain Semantics (`TestAstrophysicalConstraints`)
- **Axiom**: Astrophysical data must satisfy the laws of physics and celestial coordinate geometry:
  1. **Strictly Positive Periods**: $P > 0$ days for all physical orbits.
  2. **Bounded Eccentricity**: $0 \le e < 1.0$ for bound elliptic orbits.
  3. **Semi-Amplitude Positivity**: $K_1 > 0$ and $K_2 > 0$ where determined.
  4. **Celestial Coordinate Bounds**: $\alpha \in [0^\circ, 360^\circ]$, $\delta \in [-90^\circ, +90^\circ]$.

### Layer 6: Multi-Body Topology & Graph Integrity (`TestHierarchicalConfigurations`)
- **Axiom**: Complex hierarchical multiple systems (triples, quadruples, higher-order) must have consistent family groupings and tree connectivity (`parent`, `child1`, `child2`).
- **Target Behaviors**:
  - Validation that `in_high_order` flags identify valid tree nodes.
  - Multi-system grouping sets (`family`) correctly cluster related systems.

---

## 3. Test Suite Implementation

The test suite is formalized in [`tests/test_sbx_queries.py`](file:///C:/Dev/github/philippeback/sbx/tests/test_sbx_queries.py) and executed via `pytest`:

```powershell
uv run pytest -v
```

### Execution Guarantee
- **Speed**: Executes all 19 automated tests in `< 0.20s`.
- **Isolation**: Read-only connection mode (`mode=ro`) ensures the test suite cannot mutate production database state.
- **Reproducibility**: Parameterized test matrices ensure deterministic CI/CD validation.
