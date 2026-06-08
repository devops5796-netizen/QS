import os
import boto3
from pathlib import Path

def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["CF_R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["CF_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CF_R2_SECRET_ACCESS_KEY"],
        region_name="auto"
    )

def upload_images(images_folder: str) -> dict:
    print("\n" + "="*50)
    print("STEP 5: Uploading images to Cloudflare R2...")
    print("="*50)

    bucket = os.environ["CF_R2_BUCKET_NAME"]
    client = get_r2_client()

    uploaded = 0
    failed = 0

    image_files = list(Path(images_folder).glob("*.webp"))
    print(f"Found {len(image_files)} images to upload")

    for img_path in image_files:
        try:
            client.upload_file(
                str(img_path),
                bucket,
                f"images/{img_path.name}",
                ExtraArgs={"ContentType": "image/webp"}
            )
            uploaded += 1
            print(f"  Uploaded: {img_path.name}")
        except Exception as e:
            failed += 1
            print(f"  Failed: {img_path.name} -> {e}")

    print(f"\nSTEP 5 DONE: {uploaded} uploaded | {failed} failed")
    return {"uploaded": uploaded, "failed": failed}