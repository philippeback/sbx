# How-To: Extract and Upload SBX Dumps to Google Cloud Storage (GCS)

This guide explains how to run the SBX data extractor and automatically synchronize both the Parquet tables and metadata manifests to Google Cloud Storage.

---

## 1. Prerequisites

### Tools
- **Python >= 3.11** managed via **`uv`**.
- **Google Cloud CLI (`gcloud`)** installed via Scoop:
  ```powershell
  scoop install gcloud
  ```

### Google Cloud Infrastructure
- **GCP Project**: `hos-infra`
- **GCS Bucket**: `gs://hos-infra-sbx-data` (Location: `europe-west1`)

---

## 2. Authentication

Before running the extractor, ensure you are logged into Google Cloud:

```powershell
# Authenticate your active CLI user account
gcloud auth login

# Set active project
gcloud config set project hos-infra
```

> [!NOTE]
> The extractor will automatically pick up your active `gcloud` credentials without requiring manual service account key downloads.

---

## 3. Running the Extraction & Sync

### Option A: Upload Directly to Google Cloud Storage
Set the backend to `gcs` and specify the bucket:

```powershell
$env:SBX_STORAGE_BACKEND = "gcs"
$env:SBX_STORAGE_BUCKET  = "hos-infra-sbx-data"
uv run python extract_sbx.py
```

### Option B: Local Dump Only (No Cloud Upload)
If you want to extract locally to `./sbx_dump` without uploading to GCS:

```powershell
$env:SBX_STORAGE_BACKEND = "local"
uv run python extract_sbx.py
```

---

## 4. Storage Structure in the Bucket

When `SBX_STORAGE_BACKEND = "gcs"` is used, artifacts are structured per [docs/STORAGE_SPEC.md](../docs/STORAGE_SPEC.md):

```text
gs://hos-infra-sbx-data/sbx/
├── latest/
│   ├── manifest.json
│   ├── systems.parquet
│   ├── orbits.parquet
│   ├── velocities.parquet
│   ├── alias.parquet
│   ├── configurations.parquet
│   └── duplicates.parquet
└── snapshots/
    └── <TIMESTAMP>/ (e.g. 20261010T194007Z)
        ├── manifest.json
        ├── systems.parquet
        ├── orbits.parquet
        ├── velocities.parquet
        ├── alias.parquet
        ├── configurations.parquet
        └── duplicates.parquet
```

- **`latest/`**: Always contains the most up-to-date data dumps.
- **`snapshots/<TIMESTAMP>/`**: Immutable snapshots for versioning and reproducibility.
- **`manifest.json`**: Contains table row counts, file sizes, and SHA256 checksums.

---

## 5. Verifying & Inspecting Uploaded Data

### List Objects in the Bucket
```powershell
gcloud storage ls --recursive gs://hos-infra-sbx-data/sbx/
```

### Download the Latest Snapshot Locally
```powershell
gcloud storage cp --recursive gs://hos-infra-sbx-data/sbx/latest ./my_downloaded_sbx/
```

### Inspect the Latest Manifest
```powershell
gcloud storage cat gs://hos-infra-sbx-data/sbx/latest/manifest.json
```
