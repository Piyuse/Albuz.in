import io
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITransactionTestCase

from integrations.drive_downloads import LimitedPhotoBuffer, download_drive_photo

from .constants import MAX_PHOTO_BYTES, PHOTO_FORMATS
from .models import Album, AlbumPhoto, PhotoAsset
from .serializers import PhotoUploadSerializer


class PhotoLimitTests(APITransactionTestCase):
    def test_single_photo_accepts_300_mb_and_rejects_more(self):
        image = SimpleNamespace(format="JPEG", size=(100, 100))
        photo = SimpleNamespace(size=MAX_PHOTO_BYTES, image=image)
        serializer = PhotoUploadSerializer()

        self.assertIs(serializer.validate_photo(photo), photo)
        photo.size += 1
        with self.assertRaisesRegex(ValidationError, "300 MB"):
            serializer.validate_photo(photo)

        photo.size = MAX_PHOTO_BYTES
        photo.image.size = (10_000, 8_000)
        self.assertIs(serializer.validate_photo(photo), photo)
        photo.image.size = (10_000, 8_001)
        with self.assertRaisesRegex(ValidationError, "80 million pixels"):
            serializer.validate_photo(photo)

    def test_drive_download_spools_to_disk_and_enforces_limit(self):
        with LimitedPhotoBuffer() as buffer:
            buffer.write(b"x" * (8 * 1024 * 1024 + 1))
            self.assertTrue(buffer._rolled)

        with patch("integrations.drive_downloads.MAX_PHOTO_BYTES", 12):
            with LimitedPhotoBuffer() as buffer:
                buffer.write(b"x" * 10)
                with self.assertRaises(ValidationError):
                    buffer.write(b"abc")
                self.assertEqual(buffer.tell(), 10)

    @patch("integrations.drive_downloads.MediaIoBaseDownload")
    def test_drive_download_validates_disk_backed_image(self, downloader_class):
        image_buffer = io.BytesIO()
        Image.new("RGB", (12, 12), "blue").save(image_buffer, format="JPEG")
        image_bytes = image_buffer.getvalue()
        service = Mock()

        def fake_downloader(buffer, request, chunksize):
            downloader = Mock()

            def next_chunk(num_retries):
                buffer.write(image_bytes)
                return None, True

            downloader.next_chunk.side_effect = next_chunk
            return downloader

        downloader_class.side_effect = fake_downloader
        for drive_mime_type in ("image/jpeg", "image/jpg", "image/pjpeg"):
            with self.subTest(drive_mime_type=drive_mime_type):
                service.files.return_value.get.return_value.execute.return_value = {
                    "name": "large-original.jpg",
                    "mimeType": drive_mime_type,
                    "size": str(200 * 1024 * 1024),
                    "parents": ["test-folder"],
                    "capabilities": {"canDownload": True},
                }
                result = download_drive_photo(
                    service=service,
                    folder={"folder_id": "test-folder", "resource_key": ""},
                    file_id="photo-1",
                )
                try:
                    self.assertEqual(result["filename"], "large-original.jpg")
                    self.assertEqual(result["photo"].content_type, "image/jpeg")
                    self.assertEqual(result["photo"].size, len(image_bytes))
                    self.assertEqual((result["width"], result["height"]), (12, 12))
                finally:
                    result["photo"].close()

    @patch("integrations.drive_downloads.MediaIoBaseDownload")
    def test_mpo_jpg_from_drive_uses_jpeg_content_type(self, downloader_class):
        image_buffer = io.BytesIO()
        Image.new("RGB", (12, 12), "red").save(
            image_buffer,
            "MPO",
            save_all=True,
            append_images=[Image.new("RGB", (12, 12), "blue")],
        )
        mpo_bytes = image_buffer.getvalue()
        service = Mock()
        service.files.return_value.get.return_value.execute.return_value = {
            "name": "camera-photo.jpg",
            "mimeType": "image/jpeg",
            "size": str(len(mpo_bytes)),
            "parents": ["test-folder"],
            "capabilities": {"canDownload": True},
        }

        def fake_downloader(buffer, request, chunksize):
            downloader = Mock()

            def next_chunk(num_retries):
                buffer.write(mpo_bytes)
                return None, True

            downloader.next_chunk.side_effect = next_chunk
            return downloader

        downloader_class.side_effect = fake_downloader
        result = download_drive_photo(
            service=service,
            folder={"folder_id": "test-folder", "resource_key": ""},
            file_id="photo-1",
        )
        try:
            self.assertEqual(result["photo"].image.format, "MPO")
            self.assertEqual(result["photo"].content_type, "image/jpeg")
            self.assertEqual(PHOTO_FORMATS["MPO"], ("jpg", "image/jpeg"))
        finally:
            result["photo"].close()

    @patch("integrations.drive_downloads.MediaIoBaseDownload")
    def test_drive_metadata_mismatch_uses_verified_image_type(self, downloader_class):
        image_buffer = io.BytesIO()
        Image.new("RGB", (12, 12), "green").save(image_buffer, format="PNG")
        png_bytes = image_buffer.getvalue()
        service = Mock()
        service.files.return_value.get.return_value.execute.return_value = {
            "name": "camera-photo.jpg",
            "mimeType": "image/jpeg",
            "size": str(len(png_bytes)),
            "parents": ["test-folder"],
            "capabilities": {"canDownload": True},
        }

        def fake_downloader(buffer, request, chunksize):
            downloader = Mock()

            def next_chunk(num_retries):
                buffer.write(png_bytes)
                return None, True

            downloader.next_chunk.side_effect = next_chunk
            return downloader

        downloader_class.side_effect = fake_downloader
        result = download_drive_photo(
            service=service,
            folder={"folder_id": "test-folder", "resource_key": ""},
            file_id="photo-1",
        )
        try:
            self.assertEqual(result["photo"].content_type, "image/png")
            self.assertEqual(result["photo"].name, "drive-photo.png")
            self.assertEqual(result["filename"], "camera-photo.png")
        finally:
            result["photo"].close()


class LargeDriveImportTests(APITransactionTestCase):
    @patch("albums.drive_views.get_drive_service")
    @patch("albums.drive_views.download_drive_photo")
    def test_multiple_large_photos_are_processed_sequentially(self, download, get_service):
        user = get_user_model().objects.create_user(
            username="large_drive_import",
            email="large-drive@example.com",
            password="test-password-123",
        )
        album = Album.objects.create(owner=user, title="Large photos")
        self.client.force_authenticate(user=user)
        get_service.return_value = Mock()
        photos = []

        def fake_download(**kwargs):
            if photos:
                self.assertTrue(photos[-1].closed)
            photo = UploadedFile(
                file=io.BytesIO(b"test"),
                name="large.jpg",
                content_type="image/jpeg",
                size=200 * 1024 * 1024,
            )
            photos.append(photo)
            return {"photo": photo, "filename": "large.jpg", "width": 100, "height": 100}

        download.side_effect = fake_download
        storage = PhotoAsset._meta.get_field("file").storage
        import_url = f"/api/albums/{album.pk}/photos/import-drive/"
        payload = {
            "folder_link": "https://drive.google.com/drive/folders/test-folder",
            "photos": [{"file_id": "photo-1"}, {"file_id": "photo-2"}],
        }
        with patch.object(storage, "save", side_effect=lambda name, photo: name):
            response = self.client.post(import_url, payload, format="json")
            repeated = self.client.post(import_url, payload, format="json")
            mixed = self.client.post(
                import_url,
                {**payload, "photos": [{"file_id": "photo-1"}, {"file_id": "photo-3"}]},
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["imported"], 2)
        self.assertEqual(response.data["skipped"], 0)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.data["imported"], 0)
        self.assertEqual(repeated.data["skipped"], 2)
        self.assertEqual(mixed.status_code, 201)
        self.assertEqual(mixed.data["imported"], 1)
        self.assertEqual(mixed.data["skipped"], 1)
        self.assertEqual(download.call_count, 3)
        self.assertTrue(all(photo.closed for photo in photos))
        self.assertEqual(album.photos.count(), 3)

    @patch("albums.drive_views.get_drive_service")
    @patch("albums.drive_views.download_drive_photo")
    def test_existing_identical_photo_without_drive_id_is_skipped(self, download, get_service):
        user = get_user_model().objects.create_user(
            username="legacy_drive_import",
            email="legacy-drive@example.com",
            password="test-password-123",
        )
        album = Album.objects.create(owner=user, title="Existing photos")
        asset = PhotoAsset.objects.create(
            file="photos/legacy.jpg",
            filename="legacy.jpg",
            content_type="image/jpeg",
            size=4,
            width=10,
            height=10,
        )
        placement = AlbumPhoto.objects.create(album=album, asset=asset)
        self.client.force_authenticate(user=user)
        get_service.return_value = Mock()
        photo = UploadedFile(
            file=io.BytesIO(b"test"),
            name="legacy.jpg",
            content_type="image/jpeg",
            size=4,
        )
        download.return_value = {
            "photo": photo,
            "filename": "legacy.jpg",
            "width": 10,
            "height": 10,
        }
        storage = PhotoAsset._meta.get_field("file").storage
        with patch.object(storage, "open", side_effect=lambda name, mode: io.BytesIO(b"test")):
            with patch.object(storage, "save") as save:
                response = self.client.post(
                    f"/api/albums/{album.pk}/photos/import-drive/",
                    {
                        "folder_link": "https://drive.google.com/drive/folders/test-folder",
                        "photos": [{"file_id": "photo-1"}],
                    },
                    format="json",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["imported"], 0)
        self.assertEqual(response.data["skipped"], 1)
        self.assertEqual(album.photos.count(), 1)
        placement.refresh_from_db()
        self.assertEqual(placement.source_drive_file_id, "photo-1")
        self.assertTrue(photo.closed)
        save.assert_not_called()
