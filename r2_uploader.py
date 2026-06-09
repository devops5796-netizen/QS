import os
import boto3
from pathlib import Path

def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("CF_R2_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("CF_R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("CF_R2_SECRET_ACCESS_KEY"),
        region_name="auto"
    )

def upload_all(images_folder: str, final_csv: str) -> dict:
    print("\n" + "="*50)
    print("STEP 4: Uploading to Cloudflare R2...")
    print("="*50)

    bucket = os.environ.get("CF_R2_BUCKET_NAME")
    client = get_r2_client()
    uploaded = 0
    failed = 0

    # upload images
    image_files = list(Path(images_folder).glob("*.webp"))
    print(f"Found {len(image_files)} images to upload")
    for img_path in image_files:
        try:
            client.upload_file(
                str(img_path), bucket,
                f"images/{img_path.name}",
                ExtraArgs={"ContentType": "image/webp"}
            )
            uploaded += 1
            print(f"  Uploaded: {img_path.name}")
        except Exception as e:
            failed += 1
            print(f"  Failed: {img_path.name} -> {e}")

    # upload CSV
    try:
        client.upload_file(
            final_csv, bucket,
            f"csv/{Path(final_csv).name}",
            ExtraArgs={"ContentType": "text/csv"}
        )
        uploaded += 1
        print(f"  Uploaded CSV: {Path(final_csv).name}")
    except Exception as e:
        failed += 1
        print(f"  Failed CSV: {e}")

    print(f"\nSTEP 4 DONE: {uploaded} uploaded | {failed} failed")
    return {"uploaded": uploaded, "failed": failed}