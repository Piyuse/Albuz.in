import io
import hashlib
from django.core import signing
from django.utils import timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APITransactionTestCase

from .models import (
    Album,
    AlbumPhoto,
    AlbumShare,
    PendingPhotoDeletion,
    PhotoAsset,
)


User = get_user_model()


class AlbumSafetyTests(APITransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="safety_owner",
            email="owner@example.com",
            password="test-only-password",
        )

        self.other_user = User.objects.create_user(
            username="safety_other",
            email="other@example.com",
            password="test-only-password",
        )

        self.album = Album.objects.create(
            owner=self.owner,
            title="Source album",
        )

        self.album_url = f"/api/albums/{self.album.pk}/"

        # Replace storage deletion with a mock.
        # These tests must not delete real S3 files.
        storage = PhotoAsset._meta.get_field("file").storage
        patcher = patch.object(storage, "delete")

        self.storage_delete = patcher.start()
        self.addCleanup(patcher.stop)

    def create_asset(self):
        # Assigning a string creates only database metadata.
        # No image is uploaded to S3.
        return PhotoAsset.objects.create(
            file="photos/safety-test.jpg",
            filename="safety-test.jpg",
            content_type="image/jpeg",
            size=100,
            width=1,
            height=1,
        )

    def run_cleanup(self, delete=False):
        call_command(
            "cleanup_unused_photos",
            delete=delete,
            older_than_hours=0,
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )

    def test_other_user_cannot_delete_album(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.delete(self.album_url)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            Album.objects.filter(pk=self.album.pk).exists()
        )

    def test_deleting_source_album_preserves_copy(self):
        asset = self.create_asset()

        AlbumPhoto.objects.create(
            album=self.album,
            asset=asset,
            caption="Original placement",
            position=0,
        )

        destination = Album.objects.create(
            owner=self.other_user,
            title="Recipient album",
        )

        copied_photo = AlbumPhoto.objects.create(
            album=destination,
            asset=asset,
            caption="Copied placement",
            position=0,
        )

        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(self.album_url)

        self.assertEqual(response.status_code, 204)
        self.album.refresh_from_db()
        self.assertTrue(self.album.is_deleted)
        self.assertIsNotNone(self.album.deleted_at)
        self.assertTrue(AlbumPhoto.objects.filter(album=self.album).exists())
        self.assertEqual(self.client.get(self.album_url).status_code, 404)
        self.assertEqual(self.client.get('/api/albums/').data, [])
        self.assertTrue(
            AlbumPhoto.objects.filter(pk=copied_photo.pk).exists()
        )
        self.assertTrue(
            PhotoAsset.objects.filter(pk=asset.pk).exists()
        )
        self.storage_delete.assert_not_called()

    def test_deleting_photo_retains_record_and_removes_it_from_views(self):
        asset = self.create_asset()
        photo = AlbumPhoto.objects.create(album=self.album, asset=asset, position=0)
        token = signing.dumps(str(asset.pk), salt='album-photo')
        photo_url = f'/api/albums/{self.album.pk}/photos/{photo.pk}/'
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(photo_url)

        self.assertEqual(response.status_code, 204)
        photo.refresh_from_db()
        self.assertTrue(photo.is_deleted)
        self.assertIsNotNone(photo.deleted_at)
        self.assertTrue(PhotoAsset.objects.filter(pk=asset.pk).exists())
        self.assertEqual(self.client.get(photo_url).status_code, 404)
        self.assertEqual(self.client.get(f'/api/albums/{self.album.pk}/photos/').data['count'], 0)
        listing = self.client.get('/api/albums/').data[0]
        self.assertEqual(listing['photo_count'], 0)
        self.assertIsNone(listing['cover_url'])
        self.assertEqual(self.client.get(f'/api/albums/media/{token}/').status_code, 404)
        self.assertEqual(self.client.delete(photo_url).status_code, 404)
        self.storage_delete.assert_not_called()

    def test_other_user_cannot_delete_photo(self):
        asset = self.create_asset()
        photo = AlbumPhoto.objects.create(album=self.album, asset=asset)
        self.client.force_authenticate(user=self.other_user)

        response = self.client.delete(f'/api/albums/{self.album.pk}/photos/{photo.pk}/')

        self.assertEqual(response.status_code, 404)
        photo.refresh_from_db()
        self.assertFalse(photo.is_deleted)

    def test_deleting_album_disables_share_and_media_url(self):
        asset = self.create_asset()
        AlbumPhoto.objects.create(album=self.album, asset=asset)
        share_token = 'test-share-token'
        AlbumShare.objects.create(
            album=self.album,
            token_hash=hashlib.sha256(share_token.encode()).hexdigest(),
            expires_at=timezone.now() + timezone.timedelta(days=1),
        )
        media_token = signing.dumps(str(asset.pk), salt='album-photo')
        self.client.force_authenticate(user=self.owner)

        self.assertEqual(self.client.delete(self.album_url).status_code, 204)
        self.assertEqual(self.client.get(f'/api/albums/shared/{share_token}/photos/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/albums/media/{media_token}/').status_code, 404)
        self.assertEqual(self.client.delete(self.album_url).status_code, 404)

    def test_copy_can_restore_deleted_destination_photo(self):
        asset = self.create_asset()
        source_photo = AlbumPhoto.objects.create(album=self.album, asset=asset)
        destination = Album.objects.create(owner=self.owner, title='Destination')
        removed_photo = AlbumPhoto.objects.create(
            album=destination, asset=asset, is_deleted=True, deleted_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(f'/api/albums/{destination.pk}/photos/copy/', {
            'source_album_id': str(self.album.pk), 'photo_ids': [str(source_photo.pk)],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['copied'], 1)
        removed_photo.refresh_from_db()
        self.assertFalse(removed_photo.is_deleted)
        self.assertIsNone(removed_photo.deleted_at)
        self.assertEqual(AlbumPhoto.objects.filter(album=destination).count(), 1)

    @patch('albums.drive_views.get_drive_service')
    def test_drive_reimport_restores_deleted_photo_without_download(self, get_drive_service):
        asset = self.create_asset()
        photo = AlbumPhoto.objects.create(
            album=self.album, asset=asset, source_drive_file_id='drive-photo-1',
            is_deleted=True, deleted_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(f'/api/albums/{self.album.pk}/photos/import-drive/', {
            'folder_link': 'https://drive.google.com/drive/folders/test-folder',
            'photos': [{'file_id': 'drive-photo-1'}],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['imported'], 1)
        self.assertEqual(response.data['photo_ids'], [str(photo.pk)])
        photo.refresh_from_db()
        self.assertFalse(photo.is_deleted)
        self.assertIsNone(photo.deleted_at)
        self.assertEqual(PhotoAsset.objects.count(), 1)
        get_drive_service.assert_not_called()

    def test_cleanup_preserves_referenced_asset(self):
        asset = self.create_asset()

        AlbumPhoto.objects.create(
            album=self.album,
            asset=asset,
            position=0,
        )

        self.run_cleanup(delete=True)

        self.assertTrue(
            PhotoAsset.objects.filter(pk=asset.pk).exists()
        )
        self.assertEqual(PendingPhotoDeletion.objects.count(), 0)
        self.storage_delete.assert_not_called()

    def test_cleanup_dry_run_changes_nothing(self):
        asset = self.create_asset()

        self.run_cleanup(delete=False)

        self.assertTrue(
            PhotoAsset.objects.filter(pk=asset.pk).exists()
        )
        self.assertEqual(PendingPhotoDeletion.objects.count(), 0)
        self.storage_delete.assert_not_called()

    def test_failed_storage_deletion_can_be_retried(self):
        asset = self.create_asset()
        asset_id = asset.pk
        file_name = asset.file.name

        self.storage_delete.side_effect = RuntimeError(
            "Simulated storage failure"
        )

        with self.assertRaises(CommandError):
            self.run_cleanup(delete=True)

        # The unused asset is removed, but its file key remains queued.
        self.assertFalse(
            PhotoAsset.objects.filter(pk=asset_id).exists()
        )
        self.assertTrue(
            PendingPhotoDeletion.objects.filter(
                file_name=file_name
            ).exists()
        )

        # Make the simulated storage available again.
        self.storage_delete.side_effect = None
        self.storage_delete.reset_mock()

        self.run_cleanup(delete=True)

        self.storage_delete.assert_called_once_with(file_name)
        self.assertFalse(
            PendingPhotoDeletion.objects.filter(
                file_name=file_name
            ).exists()
        )
