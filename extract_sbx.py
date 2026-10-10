from pathlib import Path

import pandas as pd
import pyvo as vo

# TAP Endpoint
TAP_URL = "https://astro.ulb.ac.be:443/sbx/tap"
service = vo.dal.TAPService(TAP_URL)

TABLES = ["systems", "orbits", "velocities", "alias", "configurations", "duplicates"]
output_dir = Path("./sbx_dump")
output_dir.mkdir(exist_ok=True)

import io
import requests

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
        df.to_parquet(output_dir / f"{table_name}.parquet", index=False)
        print(f"Saved {table_name}: {len(df)} rows.")
    except Exception as e:
        print(f"Failed to extract {table_name}: {e}")