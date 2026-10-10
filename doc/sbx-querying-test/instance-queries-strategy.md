# Instance Querying Test Strategy & 5-Tier Complexity Spectrum (`doc/sbx-querying-test/instance-queries-strategy.md`)

## 1. Philosophical Perspective & System Intent

While model-level tests (`tests/test_sbx_queries.py`) enforce formal constraints and referential integrity (zero orphan rows, PRAGMA invariants, schema definitions), **instance-level tests** (`tests/test_sbx_instances.py`) exercise the actual semantic and astrophysical utility of the database.

To an **extreme hyper-systemizer**, human and agent querying requirements span a continuous gradient of domain depth. We categorize this spectrum into **5 Discrete Complexity Tiers**:

```
[Level 1: Mundane / Layman Searches]
       │
       ▼
[Level 2: Target Selection & Observational Planning]
       │
       ▼
[Level 3: Standard Astrophysical Characterization]
       │
       ▼
[Level 4: Statistical Outliers & Kinematic Precision]
       │
       ▼
[Level 5: Exquisite & Cutting-Edge Relativistic Research]
```

---

## 2. The 5-Tier Querying Hierarchy

### Tier 1: Mundane / Layman Searches
- **Intent**: Casual stargazing, common catalog lookup, educational checks.
- **Cognitive Load**: Low. Requires no formal knowledge of celestial mechanics.
- **Exercised Queries**:
  1. *Identifier Resolution*: Resolving a star by its common catalog number (e.g., `HIP 443`).
  2. *Naked-Eye Visibility Filter*: Locating all spectroscopic binary systems visible to the unaided human eye ($V \le 6.0$).
     ```sql
     SELECT sn, mag1, st1 FROM systems 
     WHERE mag1 IS NOT NULL AND mag1 <= 6.0 
     ORDER BY mag1 ASC;
     ```

### Tier 2: Target Selection & Observational Planning
- **Intent**: Preparing observational runs, scheduling ground-based telescope proposals, filtering by sky coordinates.
- **Cognitive Load**: Practical astronomy.
- **Exercised Queries**:
  1. *Hemispheric Visibility Windows*: Filtering targets by declination boundary ($\delta > +20^\circ$) and magnitude thresholds ($V < 8.0$) for small-to-medium observatories.
  2. *High Proper Motion Kinematics*: Identifying fast-moving systems across the celestial sphere ($\mu_{\text{total}} > 500\text{ mas/yr}$):
     ```sql
     SELECT sn, pmra, pmdec, (pmra*pmra + pmdec*pmdec) as total_pm_sq
     FROM systems
     WHERE (pmra*pmra + pmdec*pmdec) > 250000.0;
     ```

### Tier 3: Standard Astrophysical Characterization
- **Intent**: Categorizing binary star architecture, measuring orbital periods, calculating mass ratios.
- **Cognitive Load**: Undergraduate / graduate astrophysics.
- **Exercised Queries**:
  1. *Tidally Circularized Close Binaries*: Extracting systems where tidal dissipation has driven eccentricity to strictly zero ($e = 0$) in short-period configurations ($P < 10\text{ days}$).
  2. *Double-Lined Binary (SB2) Mass Ratios*: Identifying systems where both primary ($K_1$) and secondary ($K_2$) velocity semi-amplitudes are resolved, computing the mass ratio estimate ($q = K_1 / K_2$):
     ```sql
     SELECT sn, [on], K1, K2, (K1 / K2) as mass_ratio_estimate
     FROM orbits
     WHERE K1 IS NOT NULL AND K2 IS NOT NULL AND K1 > 0 AND K2 > 0;
     ```

### Tier 4: Statistical Outliers & High-Precision Kinematics
- **Intent**: Data mining for extreme astrophysical regimes, precision astrometric cuts, and time-series cadence analysis.
- **Cognitive Load**: Post-doctoral research and survey science.
- **Exercised Queries**:
  1. *Immediate Solar Neighborhood ($d < 10\text{ pc}$)*: Querying Gaia DR3 cross-matched systems with measured parallaxes $\varpi > 100\text{ mas}$.
  2. *Extreme Orbital Eccentricities ($e \ge 0.85$)*: Isolating orbital dynamics outliers approaching parabolic trajectories.
  3. *Dense Radial Velocity Time-Series*: Extracting systems with rich empirical datasets ($> 300$ individual radial velocity epochs per orbital solution) for spectroscopic re-modeling.

### Tier 5: Exquisite & Cutting-Edge Relativistic Research
- **Intent**: Discovering compact object companions (neutron stars, black holes), resolving evolutionary discordances, and analyzing multi-body hierarchical topologies.
- **Cognitive Load**: Leading-edge dynamical and relativistic astrophysics.
- **Exercised Queries**:
  1. *Hierarchical Multiple-Star Graphs*: Querying higher-order multiple star systems (`configurations.in_high_order = 1`) joined against resolved orbital solutions.
  2. *Multi-Solution Discordance*: Detecting systems with $\ge 4$ distinct published orbital determinations in the literature to study orbital precession or historical observational systematics:
     ```sql
     SELECT s.sn, COUNT(o.[on]) as num_solutions,
            MIN(o.period) as min_P, MAX(o.period) as max_P
     FROM systems s
     JOIN orbits o ON s.sn = o.sn
     GROUP BY s.sn
     HAVING num_solutions >= 4;
     ```
  3. *High-Mass Function Compact Companion Candidates*: Isolating single-lined (SB1) binaries with long periods ($P > 30\text{ d}$) and massive velocity amplitudes ($K_1 > 40\text{ km/s}$), indicative of unseen compact stellar remnants.

---

## 3. Verification Protocol

All 5 tiers are fully codified in the automated test suite [`tests/test_sbx_instances.py`](file:///C:/Dev/github/philippeback/sbx/tests/test_sbx_instances.py).

Execute the full suite:
```powershell
uv run pytest tests/test_sbx_instances.py -v
```

All 12 instance tests pass deterministically in `< 0.20s` against the read-only SQLite database.
