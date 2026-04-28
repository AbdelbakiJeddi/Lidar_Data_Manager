import sys
import os
from minio import Minio
from pymongo import MongoClient

# Add /app to sys.path to import our modules if needed, 
# but for simplicity we will just use settings from env or defaults
MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:rootpassword@mongodb:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "lidar_db")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"

BUCKET_RAW = "lidar-raw"
BUCKET_PROCESSED = "lidar-processed"

def cleanup():
    print("--- Cleaning up MongoDB ---")
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client[DB_NAME]
        
        collections = ["datasets", "octree_nodes"]
        for coll in collections:
            count = db[coll].count_documents({})
            db[coll].delete_many({})
            print(f"Deleted {count} documents from collection '{coll}'")
        
        mongo_client.close()
    except Exception as e:
        print(f"Error cleaning MongoDB: {e}")

    print("\n--- Cleaning up MinIO ---")
    try:
        minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        
        buckets = [BUCKET_RAW, BUCKET_PROCESSED]
        for bucket in buckets:
            if minio_client.bucket_exists(bucket):
                objects = minio_client.list_objects(bucket, recursive=True)
                count = 0
                for obj in objects:
                    minio_client.remove_object(bucket, obj.object_name)
                    count += 1
                print(f"Deleted {count} objects from bucket '{bucket}'")
            else:
                print(f"Bucket '{bucket}' does not exist")
    except Exception as e:
        print(f"Error cleaning MinIO: {e}")

if __name__ == "__main__":
    cleanup()
