# Agent Querying Cookbook & Relational Schema Guide (`doc/sbx-about/query-cookbook.md`)

This guide is intended for AI agents and automated pipelines querying `sbx.sqlite` or the IVOA TAP endpoint (`https://astro.ulb.ac.be:443/sbx/tap`).

---

## 1. Schema Entity Relationship Diagram

```
┌───────────────────────────┐
│          systems          │
│  sn (PK)                  │◄─────────────────┐
│  ra, dec, pmra, pmdec     │                  │
│  parallax, mag1, mag2     │                  │
│  st1, st2                 │                  │
└─────────────┬─────────────┘                  │
              │ 1:N                            │
              ▼                                │
┌───────────────────────────┐                  │
│          orbits           │                  │
│  on (PK), sn (FK)         │                  │
│  period, eccentricity     │                  │
│  K1, K2, systemic_velocity│                  │
│  bibcode, grade           │                  │
└─────────────┬─────────────┘                  │
              │ 1:N                            │
              ▼                                │
┌───────────────────────────┐                  │
│        velocities         │                  │
│  sn (FK), on (FK)         │                  │
│  epoch, radial_velocity   │                  │
│  radial_velocity_error    │                  │
│  component, weight        │                  │
└───────────────────────────┘                  │
                                               │
┌───────────────────────────┐                  │
│           alias           │                  │
│  sn (FK), catalog         │──────────────────┤
│  identifier, version      │                  │
└───────────────────────────┘                  │
                                               │
┌───────────────────────────┐                  │
│       configurations      │                  │
│  sn, parent, child1...    │──────────────────┤
│  family, in_triple...     │                  │
└───────────────────────────┘                  │
                                               │
┌───────────────────────────┐                  │
│        duplicates         │                  │
│  sn, sn_duplicate         │──────────────────┘
└───────────────────────────┘
```

---

## 2. Common Query Patterns

### Pattern A: Resolving an Identifier (e.g., HD, HIP, Gaia DR3) to System and Orbits
```sql
SELECT 
    s.sn,
    a.catalog,
    a.identifier,
    s.ra,
    s.dec,
    s.parallax,
    s.mag1,
    s.st1,
    o.period,
    o.eccentricity,
    o.K1,
    o.bibcode
FROM alias a
JOIN systems s ON a.sn = s.sn
LEFT JOIN orbits o ON s.sn = o.sn
WHERE a.identifier = 'HD 189733' -- or 'HIP 98792'
ORDER BY o.grade DESC;
```

### Pattern B: Cone Search Around Celestial Coordinates (RA/Dec in degrees)
```sql
-- Approx. box filter followed by angular distance
SELECT 
    sn, ra, dec, parallax, pmra, pmdec, mag1, st1
FROM systems
WHERE ra BETWEEN 295.0 AND 297.0
  AND dec BETWEEN 40.0 AND 42.0;
```

### Pattern C: Extracting Full Radial Velocity Curve for an Orbit
```sql
SELECT 
    v.epoch,
    v.radial_velocity,
    v.radial_velocity_error,
    v.component,
    v.weight,
    o.period,
    o.periastron_time,
    o.eccentricity
FROM velocities v
JOIN orbits o ON v.sn = o.sn AND v.on = o.on
WHERE o.on = 1234
ORDER BY v.epoch ASC;
```

### Pattern D: Identifying Multi-Body Hierarchical Systems (Triples / Quadruples)
```sql
SELECT 
    c.sn,
    c.family,
    c.parent,
    c.child1,
    c.child2,
    c.in_triple,
    c.in_quadruple,
    c.in_high_order,
    s.ra,
    s.dec
FROM configurations c
JOIN systems s ON c.sn = s.sn
WHERE c.in_high_order = 'true' OR c.in_triple = 'true';
```

### Pattern E: High-Mass Compact Companion Candidates (Single-Lined Binaries with High RV Amplitude and Long Period)
```sql
SELECT 
    s.sn,
    s.mag1,
    s.st1,
    o.period,
    o.K1,
    o.eccentricity,
    o.bibcode
FROM orbits o
JOIN systems s ON o.sn = s.sn
WHERE o.K2 IS NULL -- Single-lined (SB1)
  AND o.K1 > 50.0   -- High velocity amplitude (km/s)
  AND o.period > 10.0
ORDER BY o.K1 DESC
LIMIT 50;
```

---

## 3. Important Domain Caveats for Agents
1. **Multiple Orbits per System**: A single `systems.sn` can have multiple rows in `orbits`. Always check `grade` or filter by preferred `bibcode` when selecting a representative orbit.
2. **Double-Lined vs. Single-Lined**:
   - Single-lined binary (SB1): `K1` is populated; `K2` is `NULL`.
   - Double-lined binary (SB2): Both `K1` and `K2` are populated.
3. **Circular Orbits**: When eccentricity is strictly 0, `periastron_argument` ($\omega$) and `periastron_time` ($T_0$) are conventionally fixed to zero.
4. **Duplicates Table**: Always check if a system `sn` appears in `duplicates` to avoid counting merged systems twice in statistical studies.
