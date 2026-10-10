import io
import json
from pathlib import Path
import pandas as pd
import pyvo as vo
import requests

from storage import StorageManager, compute_sha256

# TAP Endpoint
TAP_URL = "https://astro.ulb.ac.be:443/sbx/tap"
service = vo.dal.TAPService(TAP_URL)

TABLES = ["systems", "orbits", "velocities", "alias", "configurations", "duplicates"]
output_dir = Path("./sbx_dump")
output_dir.mkdir(exist_ok=True)

storage_mgr = StorageManager()
manifest_tables = {}

for table_name in TABLES:
    print(f"Extracting {table_name}...")
    query = f"SELECT * FROM {table_name}"
    
    # Run TAP query (sync or async)
    try:
        try:
            job = service.run_sync(query)
            df = job.to_table().to_pandas()
        except Exception as pyvo_err:
            # Fall back to CSV request if VOTable binary decoding fails (e.g. non-ASCII chars)
            resp = requests.post(
                f"{TAP_URL}/sync",
                data={"REQUEST": "doQuery", "LANG": "ADQL", "QUERY": query, "FORMAT": "csv"},
                timeout=120,
            )
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
        
        # Save locally as Parquet
        target_file = output_dir / f"{table_name}.parquet"
        df.to_parquet(target_file, index=False)
        print(f"Saved {table_name}: {len(df)} rows.")

        manifest_tables[table_name] = {
            "rows": len(df),
            "size_bytes": target_file.stat().st_size,
            "sha256": compute_sha256(target_file),
        }
    except Exception as e:
        print(f"Failed to extract {table_name}: {e}")

# Generate and write local manifest
manifest = storage_mgr.generate_manifest(files_info=manifest_tables, endpoint=TAP_URL)
with open(output_dir / "manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
print("Manifest written to sbx_dump/manifest.json")

# Cloud sync if enabled (SBX_STORAGE_BACKEND=gcs)
if storage_mgr.backend == "gcs":
    print("Initiating cloud storage upload according to STORAGE_SPEC...")
    storage_mgr.sync_to_cloud(local_dir=output_dir, manifest=manifest)