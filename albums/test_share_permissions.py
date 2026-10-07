import hashlib
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITransactionTestCase

from .models import Album, AlbumPhoto, AlbumShare, PhotoAsset


User = get_user_model()


class SharePermissionTests(APITransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="share_owner",
            email="share-owner@example.com",
            password="test-only-password",
        )

        self.recipient = User.objects.create_user(
            username="share_recipient",
            email="share-recipient@example.com",
            password="test-only-password",
        )

        self.source_album = Album.objects.create(
            owner=self.owner,
            title="Shared memories",
        )

        self.destination_album = Album.objects.create(
            owner=self.recipient,
            title="My collected memories",
        )

        self.asset = PhotoAsset.objects.create(
            file="photos/share-test.jpg",
            filename="share-test.jpg",
            content_type="image/jpeg",
            size=100,
            width=1,
            height=1,
        )

        self.source_photo = AlbumPhoto.objects.create(
            album=self.source_album,
            asset=self.asset,
            caption="Original caption",
            position=0,
        )

        self.token = "test-share-token"

        self.share = AlbumShare.objects.create(
            album=self.source_album,
            token_hash=hashlib.sha256(
                self.token.encode("utf-8")
            ).hexdigest(),
            can_copy=False,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.view_url = (
            f"/api/albums/shared/{self.token}/photos/"
        )
        self.copy_url = f"{self.view_url}copy/"

        # Prevent real storage operations and URL signing.
        storage = PhotoAsset._meta.get_field("file").storage
        self.storage_mocks = {}

        for method in ("save", "delete", "url"):
            patcher = patch.object(
                storage,
                method,
                return_value="https://example.test/photo.jpg",
            )

            self.storage_mocks[method] = patcher.start()
            self.addCleanup(patcher.stop)

    def allow_copy(self):
        self.share.can_copy = True
        self.share.save(update_fields=["can_copy"])

    def copy_photo(self, destination=None):
        if destination is None:
            destination = self.destination_album

        self.client.force_authenticate(user=self.recipient)

        return self.client.post(
            self.copy_url,
            {
                "destination_album_id": str(destination.pk),
                "photo_ids": [str(self.source_photo.pk)],
            },
            format="json",
        )

    def test_view_only_link_allows_viewing_but_denies_copy(self):
        view_response = self.client.get(self.view_url)
        self.assertEqual(view_response.status_code, 200)

        copy_response = self.copy_photo()
        self.assertEqual(copy_response.status_code, 403)

        self.assertFalse(
            AlbumPhoto.objects.filter(
                album=self.destination_album
            ).exists()
        )

    def test_copy_reuses_asset_and_has_independent_caption(self):
        self.allow_copy()

        response = self.copy_photo()
        self.assertEqual(response.status_code, 201)

        copied_photo = AlbumPhoto.objects.get(
            album=self.destination_album,
            asset=self.asset,
        )

        self.assertNotEqual(
            copied_photo.pk,
            self.source_photo.pk,
        )
        self.assertEqual(copied_photo.asset_id, self.asset.pk)
        self.assertEqual(copied_photo.caption, "Original caption")
        self.assertEqual(PhotoAsset.objects.count(), 1)

        self.storage_mocks["save"].assert_not_called()
        self.storage_mocks["delete"].assert_not_called()

        copied_photo.caption = "My own caption"
        copied_photo.save(update_fields=["caption"])

        self.source_photo.refresh_from_db()
        self.assertEqual(
            self.source_photo.caption,
            "Original caption",
        )

    def test_expired_link_denies_viewing_and_copying(self):
        self.allow_copy()

        self.share.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        self.share.save(update_fields=["expires_at"])

        self.assertEqual(
            self.client.get(self.view_url).status_code,
            404,
        )
        self.assertEqual(self.copy_photo().status_code, 404)

        self.assertFalse(
            AlbumPhoto.objects.filter(
                album=self.destination_album
            ).exists()
        )

    def test_owner_can_revoke_link(self):
        self.allow_copy()
        self.client.force_authenticate(user=self.owner)

        revoke_url = (
            f"/api/albums/{self.source_album.pk}/"
            f"shares/{self.share.pk}/"
        )

        response = self.client.delete(revoke_url)
        self.assertEqual(response.status_code, 204)

        self.share.refresh_from_db()
        self.assertIsNotNone(self.share.revoked_at)

        self.assertEqual(
            self.client.get(self.view_url).status_code,
            404,
        )
        self.assertEqual(self.copy_photo().status_code, 404)

    def test_recipient_cannot_copy_into_someone_elses_album(self):
        self.allow_copy()

        response = self.copy_photo(
            destination=self.source_album
        )

        self.assertEqual(response.status_code, 404)

        self.assertEqual(
            AlbumPhoto.objects.filter(
                album=self.source_album
            ).count(),
            1,
        )
        self.assertFalse(
            AlbumPhoto.objects.filter(
                album=self.destination_album
            ).exists()
        )

    def test_repeated_copy_does_not_duplicate_photo(self):
        self.allow_copy()

        first_response = self.copy_photo()
        second_response = self.copy_photo()

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)

        self.assertEqual(
            AlbumPhoto.objects.filter(
                album=self.destination_album,
                asset=self.asset,
            ).count(),
            1,
        )
        self.assertEqual(PhotoAsset.objects.count(), 1)
        self.storage_mocks["save"].assert_not_called()