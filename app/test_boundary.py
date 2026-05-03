import asyncio
from app.services.pdal_processor import PDALProcessor
from app.core.minio_client import get_minio_client
import tempfile
from minio import Minio

def main():
    import json
    import subprocess
    proc = PDALProcessor()
    
    # We will use MC to download the file from minio to a local temp file? No, we can just use minio client.
    # Actually, we don't need minio. We can just use curl.
    # I'll just write it.
