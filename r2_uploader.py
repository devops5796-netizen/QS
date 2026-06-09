import os
import mimetypes
from pathlib import Path
import boto3

CF_R2_ACCESS_KEY = os.getenv('CF_R2_ACCESS_KEY_ID')
CF_R2_SECRET_KEY = os.getenv('CF_R2_SECRET_ACCESS_KEY')
CF_R2_ENDPOINT_URL = os.getenv('CF_R2_ENDPOINT_URL')
BUCKET_NAME = os.getenv('CF_R2_BUCKET_NAME', '')

CLEAN_ENDPOINT = ""
if CF_R2_ENDPOINT_URL:
    CLEAN_ENDPOINT = CF_R2_ENDPOINT_URL.rstrip("/").removesuffix("/" + BUCKET_NAME)


def get_r2_client():
    if CF_R2_ACCESS_KEY and CF_R2_SECRET_KEY and CLEAN_ENDPOINT:
        try:
            return boto3.client(
                's3',
                endpoint_url=CLEAN_ENDPOINT,
                aws_access_key_id=CF_R2_ACCESS_KEY,
                aws_secret_access_key=CF_R2_SECRET_KEY,
                region_name='auto'
            )
        except Exception as e:
            print(f"Failed to initialize R2 Client: {e}")
            return None
    print("Warning: R2 Environment variables are missing.")
    return None

R2_CLIENT_INSTANCE = get_r2_client()


def upload_single_file(local_path: str, r2_folder: str = "images") -> bool:
    client = R2_CLIENT_INSTANCE if R2_CLIENT_INSTANCE else get_r2_client()
    if not client or not BUCKET_NAME:
        return False
    
    filename = Path(local_path).name
    r2_key = f"{r2_folder}/{filename}"
    
    try:
        content_type, _ = mimetypes.guess_type(local_path)
        if not content_type:
            content_type = 'image/jpeg' if r2_folder == "images" else 'application/octet-stream'

        client.upload_file(
            local_path, BUCKET_NAME, r2_key,
            ExtraArgs={"ContentType": content_type}
        )
        print(f"  [OK] Uploaded to R2: {r2_key}")
        return True
    except Exception as e:
        print(f"  [ERROR] R2 upload failed for {filename}: {e}")
        return False


def upload_final_batch_assets(images_folder: str, final_csv: str) -> dict:
    print("\n" + "="*50)
    print("STEP 4: Uploading final CSV artifact to Cloudflare R2...")
    print("="*50)
    
    uploaded = 0
    failed = 0
    
    if os.path.exists(final_csv):
        print(f"Found final flat CSV file '{final_csv}', starting upload...")
        success = upload_single_file(final_csv, r2_folder="csv")
        if success:
            uploaded += 1
            print("-> Final CSV Artifact Uploaded successfully to R2!")
        else:
            failed += 1
            print("-> [ERROR] Failed to upload final CSV to R2.")
    else:
        print(f"-> [WARNING] CSV Artifact NOT found at: {final_csv}")
        failed += 1
        
    return {"uploaded": uploaded, "failed": failed}