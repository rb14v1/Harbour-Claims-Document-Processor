import io
import os

from django.conf import settings
from django.test import TestCase

from apps.common import blob_store


class BlobStoreStubTests(TestCase):
    def test_upload_and_download_roundtrip(self):
        content = b"Vendor: Acme Corp\nAmount: 123.45\nDate: 2024-01-15\n"
        file_obj = io.BytesIO(content)
        file_obj.name = "receipt.txt"

        blob_path = blob_store.upload_document(file_obj, container="test-container", blob_name="receipt.txt")

        self.assertIn("blob_stub/test-container/receipt.txt", blob_path)
        full_path = os.path.join(settings.MEDIA_ROOT, blob_path)
        self.assertTrue(os.path.exists(full_path))

        downloaded = blob_store.download_document(blob_path)
        self.assertEqual(downloaded, content)

    def test_upload_overwrites_existing_blob(self):
        file_obj = io.BytesIO(b"version one")
        blob_store.upload_document(file_obj, container="test-container", blob_name="overwrite.txt")

        file_obj2 = io.BytesIO(b"version two")
        blob_path = blob_store.upload_document(file_obj2, container="test-container", blob_name="overwrite.txt")

        self.assertEqual(blob_store.download_document(blob_path), b"version two")
