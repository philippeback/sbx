"""Storage backend implementation for SBX dumps adhering to docs/STORAGE_SPEC.md."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from google.cloud import storage as gcs_storage
except ImportError:
    gcs_storage = None


def compute_sha256(filepath: Path) -> str:
    """Computes SHA256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class StorageManager:
    """Manages local storage and remote cloud uploads (GCS / S3-compatible)."""

    def __init__(
        self,
        backend: Optional[str] = None,
        bucket_name: Optional[str] = None,
        prefix: Optional[str] = None,
    ):
        self.backend = (backend or os.getenv("SBX_STORAGE_BACKEND", "local")).lower()
        self.bucket_name = bucket_name or os.getenv("SBX_STORAGE_BUCKET")
        self.prefix = (prefix or os.getenv("SBX_STORAGE_PREFIX", "sbx")).strip("/")

        if self.backend == "gcs" and not self.bucket_name:
            raise ValueError("SBX_STORAGE_BUCKET environment variable must be set when backend is 'gcs'")

        self.gcs_client = None
        self.gcs_bucket = None
        if self.backend == "gcs":
            if gcs_storage is None:
                raise ImportError("google-cloud-storage is required for GCS backend. Run: uv add google-cloud-storage")
            try:
                self.gcs_client = gcs_storage.Client()
            except Exception:
                # Fallback to gcloud access token if ADC is not explicitly configured
                import subprocess
                from google.oauth2.credentials import Credentials
                token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True, shell=True).strip()
                creds = Credentials(token)
                self.gcs_client = gcs_storage.Client(credentials=creds, project=os.getenv("CLOUDSDK_CORE_PROJECT", "hos-infra"))
            self.gcs_bucket = self.gcs_client.bucket(self.bucket_name)

    def generate_manifest(
        self,
        files_info: Dict[str, Dict[str, Any]],
        endpoint: str = "https://astro.ulb.ac.be:443/sbx/tap",
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        ts = timestamp or datetime.now(timezone.utc)
        return {
            "version": "1.0.0",
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endpoint": endpoint,
            "tables": files_info,
        }

    def sync_to_cloud(self, local_dir: Path, manifest: Dict[str, Any]) -> None:
        """Uploads files and manifest to snapshots/<timestamp>/ and mirrors to latest/."""
        if self.backend != "gcs":
            print(f"Storage backend is '{self.backend}'. Skipping remote cloud upload.")
            return

        ts_folder = manifest["timestamp"].replace("-", "").replace(":", "")

        snapshot_prefix = f"{self.prefix}/snapshots/{ts_folder}"
        latest_prefix = f"{self.prefix}/latest"

        # 1. Upload parquet files
        for table_name, info in manifest["tables"].items():
            filename = f"{table_name}.parquet"
            local_file = local_dir / filename
            if not local_file.exists():
                continue

            snapshot_blob = f"{snapshot_prefix}/{filename}"
            latest_blob = f"{latest_prefix}/{filename}"

            print(f"Uploading {filename} -> gs://{self.bucket_name}/{snapshot_blob} ...")
            blob = self.gcs_bucket.blob(snapshot_blob)
            blob.upload_from_filename(str(local_file))

            print(f"Mirroring {filename} -> gs://{self.bucket_name}/{latest_blob} ...")
            blob_latest = self.gcs_bucket.blob(latest_blob)
            blob_latest.upload_from_filename(str(local_file))

        # 2. Upload manifest
        manifest_json = json.dumps(manifest, indent=2)
        for target_prefix in (snapshot_prefix, latest_prefix):
            manifest_blob_name = f"{target_prefix}/manifest.json"
            print(f"Uploading manifest -> gs://{self.bucket_name}/{manifest_blob_name} ...")
            blob = self.gcs_bucket.blob(manifest_blob_name)
            blob.upload_from_string(manifest_json, content_type="application/json")

        print("Cloud sync completed successfully.")
