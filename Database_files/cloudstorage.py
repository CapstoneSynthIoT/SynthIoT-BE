import os
from google.cloud import storage
from google.oauth2 import service_account


def _get_storage_client() -> storage.Client:
    """Create a GCS client using the service account key file from env, or fallback to Cloud Run ADC."""
    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gcp-key.json")
    
    # If the JSON file exists (like on your local dev machine), use it
    if os.path.exists(key_path):
        credentials = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return storage.Client(credentials=credentials)
    
    # Otherwise, we are running in Cloud Run! 
    # Let Google automatically handle the authentication securely.
    return storage.Client()


def upload_to_bucket(file_content: str, destination_blob_name: str) -> str:
    """Uploads a string/CSV content to the GCS bucket and returns the public URL."""
    bucket_name = os.getenv("GCP_BUCKET_NAME")
    storage_client = _get_storage_client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(file_content, content_type="text/csv")
    return f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"


def replace_in_bucket(file_bytes: bytes, blob_name: str) -> str:
    """
    Overwrites an existing GCS blob in-place with new bytes content.
    The blob_name is the object path within the bucket (e.g. 'synthetic_data_abc123.csv').
    Returns the same public URL (unchanged, since the blob name stays the same).
    """
    bucket_name = os.getenv("GCP_BUCKET_NAME")
    storage_client = _get_storage_client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(file_bytes, content_type="text/csv")
    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"