# Google Cloud Storage (GCS) Beginner's Guide & Setup for SBX

## 1. What is Google Cloud Storage (GCS)?

Think of Google Cloud Storage as a virtually infinite folder in the cloud:
* **Bucket**: A top-level container/drive that holds your data (must have a globally unique name, e.g. `sbx-dumps-philippe`).
* **Object**: Any individual file stored inside the bucket (e.g. `sbx/latest/orbits.parquet`).
* **S3-Style Compatibility**: GCS supports both native Google APIs and standard S3-compatible APIs (using HMAC keys), meaning tools designed for Amazon S3 can also read/write directly to GCS.

---

## 2. Tools Installed & Setup

### A. Python Client Library (Already Installed)
The official Google Cloud Storage client has been added to the project's virtual environment:
```powershell
uv add google-cloud-storage
```
This enables Python scripts to upload, download, and inspect objects in GCS without needing any external CLI tools.

### B. Google Cloud CLI (`gcloud`)
You can install the `gcloud` CLI on Windows using either **Scoop** or **winget**:

#### Option 1: Via Scoop (Recommended for user-space package management)
```powershell
scoop install gcloud
```

#### Option 2: Via winget
```powershell
winget install Google.CloudSDK --accept-package-agreements --accept-source-agreements
```


---

## 3. Quick 3-Step Setup on Google Cloud

### Step 1: Create a Project
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown at the top left and select **New Project**.
3. Name it (e.g., `sbx-archive`) and click **Create**.

### Step 2: Create a Storage Bucket
1. In the search bar at the top, type **Cloud Storage** and click **Buckets**.
2. Click **+ Create**.
3. **Bucket Name**: Enter a globally unique name (e.g., `sbx-data-archive-<your-initials>`).
4. **Location Type**: Choose **Region** and pick a location close to you (e.g., `europe-west1` in Belgium).
5. **Storage Class**: Select **Standard**.
6. Keep the remaining settings at default and click **Create**.

### Step 3: Authenticate for Local Access

Choose either of the two authentication methods:

#### Method A: User Login via CLI (Easiest for local development)
Once `gcloud` is installed, run:
```powershell
gcloud auth application-default login
```
This opens a browser window. Once you sign in with your Google account, credentials are automatically saved locally and used by `google-cloud-storage` in Python.

#### Method B: Service Account Key (Best for automation & headless machines)
1. Go to **IAM & Admin** > **Service Accounts** in Google Cloud Console.
2. Click **+ Create Service Account**, name it (e.g., `sbx-uploader`), and grant the role **Storage Object Admin**.
3. Click the created service account > **Keys** tab > **Add Key** > **Create new key** (JSON).
4. Download the JSON key file and set the environment variable in your terminal:
   ```powershell
   $env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\service-account-key.json"
   ```

---

## 4. Example: Uploading Parquet Files in Python

```python
from pathlib import Path
from google.cloud import storage

def upload_sbx_dumps(bucket_name: str, local_dir: str = "./sbx_dump"):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    local_path = Path(local_dir)

    for file_path in local_path.glob("*.parquet"):
        destination_blob_name = f"sbx/latest/{file_path.name}"
        blob = bucket.blob(destination_blob_name)
        
        print(f"Uploading {file_path.name} to gs://{bucket_name}/{destination_blob_name}...")
        blob.upload_from_filename(str(file_path))
        print(f"Uploaded {file_path.name} successfully.")

if __name__ == "__main__":
    # Replace with your actual bucket name
    BUCKET_NAME = "sbx-data-archive-sample"
    upload_sbx_dumps(BUCKET_NAME)
```
