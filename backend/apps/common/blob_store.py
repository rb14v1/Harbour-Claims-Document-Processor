"""
Thin wrapper around azure-storage-blob.

Real `BlobServiceClient` is used when AZURE_STORAGE_CONNECTION_STRING is set.
Otherwise falls back to writing/reading files under MEDIA_ROOT/blob_stub/ on
local disk. Both paths expose the same function signatures so callers never
need to know which mode is active.
"""

import os

from decouple import config
from django.conf import settings

AZURE_STORAGE_CONNECTION_STRING = config("AZURE_STORAGE_CONNECTION_STRING", default="")

STUB_PREFIX = "blob_stub"


def _is_real():
    return bool(AZURE_STORAGE_CONNECTION_STRING)


def _stub_dir(container):
    path = os.path.join(settings.MEDIA_ROOT, STUB_PREFIX, container)
    os.makedirs(path, exist_ok=True)
    return path


def _read_file_bytes(file_obj):
    file_obj.seek(0)
    if hasattr(file_obj, "chunks"):
        return b"".join(chunk for chunk in file_obj.chunks())
    return file_obj.read()


def upload_document(file_obj, container, blob_name):
    """
    Uploads `file_obj` (a Django UploadedFile or any file-like object) to
    `container`/`blob_name`. Returns a blob path/URL that can later be passed
    to `download_document`.
    """
    data = _read_file_bytes(file_obj)

    if _is_real():
        from azure.storage.blob import BlobServiceClient

        client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        try:
            client.create_container(container)
        except Exception:
            pass  # container already exists
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        blob_client.upload_blob(data, overwrite=True)
        return blob_client.url

    dir_path = _stub_dir(container)
    full_path = os.path.join(dir_path, blob_name)
    with open(full_path, "wb") as f:
        f.write(data)
    return f"{STUB_PREFIX}/{container}/{blob_name}"


def download_document(blob_path):
    """
    Returns the raw bytes for a blob path/URL previously returned by
    `upload_document`.
    """
    if _is_real() and str(blob_path).startswith("http"):
        from azure.storage.blob import BlobClient

        blob_client = BlobClient.from_blob_url(
            blob_path, credential=None
        ) if "://" in str(blob_path) and AZURE_STORAGE_CONNECTION_STRING else None
        if blob_client is None:
            from azure.storage.blob import BlobServiceClient

            client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
            # blob_path looks like https://<account>.blob.core.windows.net/<container>/<blob>
            parts = blob_path.split("/")
            container, blob_name = parts[-2], parts[-1]
            blob_client = client.get_blob_client(container=container, blob=blob_name)
        return blob_client.download_blob().readall()

    full_path = os.path.join(settings.MEDIA_ROOT, blob_path)
    with open(full_path, "rb") as f:
        return f.read()
