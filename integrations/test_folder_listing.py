from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from albums.models import Album, AlbumPhoto, PhotoAsset


class GoogleFolderListingTests(APITestCase):
    @patch("integrations.views.get_drive_service")
    def test_first_page_does_not_require_page_token(self, get_drive_service):
        user = get_user_model().objects.create_user(
            username="drive_folder_test",
            email="drive-folder@example.com",
            password="test-password-123",
        )
        self.client.force_authenticate(user=user)
        album = Album.objects.create(owner=user, title="Travel")
        asset = PhotoAsset.objects.create(
            file="photos/existing.jpg",
            filename="Existing.jpg",
            content_type="image/jpeg",
            size=100,
            width=10,
            height=10,
        )
        AlbumPhoto.objects.create(
            album=album,
            asset=asset,
            source_drive_file_id="photo-1",
        )

        service = Mock()
        service.files.return_value.get.return_value.execute.return_value = {
            "id": "test-folder",
            "name": "Travel",
            "mimeType": "application/vnd.google-apps.folder",
        }
        service.files.return_value.list.return_value.execute.return_value = {
            "files": [
                {"id": "photo-1", "name": "Photo.jpg"},
                {"id": "photo-2", "name": "Another.jpg"},
            ],
        }
        get_drive_service.return_value = service

        response = self.client.get(
            "/api/integrations/google/folder-photos/",
            {
                "folder_link": "https://drive.google.com/drive/folders/test-folder",
                "album_id": str(album.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["folder"]["name"], "Travel")
        self.assertEqual(response.data["files"][0]["id"], "photo-1")
        self.assertTrue(response.data["files"][0]["already_imported"])
        self.assertFalse(response.data["files"][1]["already_imported"])
        self.assertIsNone(service.files.return_value.list.call_args.kwargs["pageToken"])
        self.assertIn("mimeType = 'image/jpeg'", service.files.return_value.list.call_args.kwargs["q"])
        service.close.assert_called_once()

        AlbumPhoto.objects.filter(album=album).update(is_deleted=True)
        response = self.client.get(
            "/api/integrations/google/folder-photos/",
            {
                "folder_link": "https://drive.google.com/drive/folders/test-folder",
                "album_id": str(album.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["files"][0]["already_imported"])
