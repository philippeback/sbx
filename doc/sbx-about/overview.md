# SBX Introductory Notes & Catalogue Overview

**Source URL:** https://www.astro.ulb.ac.be/sbx/intro/  
**Online Since:** 2025-06-24  
**Maintainers:** Simon Alexandre & Thibault Merle (Université Libre de Bruxelles - ULB)

---

## 1. Presentation & Heritage

SBX (the **eXtended Catalogue of Spectroscopic Binary Orbits**) originated from the complete modernization and migration of the historic **SB9** catalogue, undertaken as part of Simon Alexandre’s Master’s thesis in Data Science at ULB (2024/2025).

### Key Evolution from SB8/SB9 to SBX:
* **SB8 (1989)**: Batten, Fletcher, Mac Carthy (Publ. DAO, V.17) contained orbits published up to Jan 1, 1988 on paper.
* **SB9 (2004–2021)**: Led by the late Dimitri Pourbaix (ULB), transitioning to electronic dissemination via the web with multi-orbit storage and individual radial velocities.
* **SBX (2025+)**: Re-architectured from flat text/catalogue files into a **relational SQL database with strict relational integrity, formal constraints, and foreign keys**.
* **Enriched Astrometry**: Systematically cross-matched and enriched with high-precision Gaia DR3 astrometry (parallaxes, proper motions, coordinates) and external catalogues (Hipparcos, Tycho, 2MASS, Simbad).
* **Reference Manuscript**: Master's thesis on the migration by Simon Alexandre: [MasterThesis_BGDA.pdf](https://astro.ulb.ac.be/sbx/static_django/home/docs/MasterThesis_BGDA.pdf).

---

## 2. Relational Architecture & The Six Core Tables

The SBX relational schema consists of six core tables:

### 1. `systems` (Parent Astronomical Objects)
Contains fundamental observational properties of the stellar system:
- Coordinates (`ra`, `dec`, `ra_error`, `dec_error`, `position_epoch`, `position_source`).
- Legacy 1900/2000 coordinate strings (`coordinates_1900_legacy`, `coordinates_2000_legacy`).
- Kinematics: Proper motions (`pmra`, `pmdec`, errors, epochs, source) and Parallaxes (`parallax`, `parallax_error`, source).
- Photometry: Magnitudes & passbands (`mag1`, `band1`, `mag2`, `band2`, sources).
- Spectroscopy: Spectral classifications (`st1`, `st1_bibcode`, `st2`, `st2_bibcode`).
- Primary Key / Identifier: `sn` (System Number).

### 2. `orbits` (Orbital Solutions)
Stores individual orbital determinations (a system may have multiple competing or historical solutions):
- Relational Link: `sn` (references `systems.sn`), `on` (Orbit Number).
- Periods & Timing: `period` (days), `period_error`, `periastron_time` (epoch/BJD/HJD), `periastron_time_error`, `periastron_time_flag`, `epoch_reference`.
- Elements: `eccentricity`, `eccentricity_error`, `periastron_argument` ($\omega$), `periastron_argument_error`.
- Velocity Amplitudes & Systemic Velocities:
  - `K1`, `K1_error` (Primary RV semi-amplitude).
  - `K2`, `K2_error` (Secondary RV semi-amplitude).
  - `systemic_velocity` ($V_0$ / $\gamma$), `systemic_velocity_error`.
  - Apparent systemic velocities for individual components: `apparent_systemic_velocity_1`, `apparent_systemic_velocity_2`.
- Quality & Provenance:
  - `grade` & `grade_legacy` (historical SB8 quality grading 5=definitive down to 1=poor).
  - `num_RV1`, `num_RV2`, `rms_RV1`, `rms_RV2` (number of measurements and residuals).
  - `bibcode` (ADS bibliographic reference code), `contributor`, `note`.

### 3. `velocities` (Individual Radial Velocity Time-Series)
Stores empirical radial velocity observations associated with orbital solutions:
- Relational Link: `sn` (references `systems.sn`), `on` (references `orbits.on`).
- Measurements: `epoch` (observation timestamp), `radial_velocity` (km/s), `radial_velocity_error` (km/s).
- Attributes: `component` (`a` = primary, `b` = secondary), `weight`, `velocity_source`, `offset_legacy`, `comment_legacy`.

### 4. `alias` (Catalogue Cross-Identifications)
Maintains cross-references with all major external astronomical catalogues:
- Relational Link: `sn` (references `systems.sn`).
- Columns: `catalog` (e.g. `HD`, `HIP`, `BD`, `Gaia DR3`, `TYC`, `Simbad`), `identifier`, `version`.

### 5. `configurations` (Hierarchical & Multiple Systems Topology)
Captures the hierarchical tree structure for higher-order multiple star systems (triples, quadruples, higher-order multiples):
- Relational Links: `sn`, `parent`, `child1`, `child2`.
- Flags & Hierarchy: `family`, `in_triple`, `in_quadruple`, `in_high_order`.
- Designed with input from Andrei Tokovinin (CTIO, Multiple Star Catalog / MSC architect).

### 6. `duplicates` (SB9 Discovered Duplications)
Tracks historic duplicate entries uncovered in SB9 during the migration to SBX:
- Columns: `sn`, `sn_duplicate`.

---

## 3. Acknowledgements & Community Collaborators

* **CDS (Centre de Données astronomiques de Strasbourg)**: Cécile Loup, Gilles Landais, Anaïs Oberto, and Gregory Mantelet for assistance in setting up the Simbad Name Resolver and IVOA TAP service.
* **ULB**: Alain Jorissen and Sophie Van Eck.
* **CTIO**: Andrei Tokovinin for architecture consultations regarding higher-order multiple systems.
* **In Memoriam**: **Dimitri Pourbaix** (1969–2021), long-time principal maintainer of SB9.
