import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APITransactionTestCase

from .models import (
    Album,
    AlbumPhoto,
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
        self.assertFalse(
            Album.objects.filter(pk=self.album.pk).exists()
        )
        self.assertTrue(
            AlbumPhoto.objects.filter(pk=copied_photo.pk).exists()
        )
        self.assertTrue(
            PhotoAsset.objects.filter(pk=asset.pk).exists()
        )
        self.storage_delete.assert_not_called()

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