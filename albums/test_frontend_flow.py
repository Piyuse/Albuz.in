import io
import tempfile
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APITransactionTestCase

from .models import PhotoAsset


class FrontendAlbumFlowTests(APITransactionTestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        storages = dict(settings.STORAGES)
        storages['default'] = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
        override = self.settings(STORAGES=storages, MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.owner = get_user_model().objects.create_user(
            username='album_owner', email='album-owner@example.com', password='test-password-123'
        )
        self.client.force_authenticate(user=self.owner)

    def test_create_upload_and_read_saved_album(self):
        created = self.client.post('/api/albums/', {
            'title': 'A mountain weekend', 'description': 'Our trip',
            'category': 'Travel', 'color': '#536a65',
        }, format='json')
        self.assertEqual(created.status_code, 201)
        album_id = created.data['id']

        image = Image.new('RGB', (12, 12), color='red')
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        uploaded = self.client.post(
            f'/api/albums/{album_id}/photos/upload/',
            {'photo': SimpleUploadedFile('summit.jpg', buffer.getvalue(), content_type='image/jpeg'), 'caption': 'At the summit'},
            format='multipart',
        )
        self.assertEqual(uploaded.status_code, 201)

        listing = self.client.get('/api/albums/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data[0]['photo_count'], 1)
        self.assertEqual(listing.data[0]['category'], 'Travel')
        self.assertTrue(listing.data[0]['cover_url'])

        photos = self.client.get(f'/api/albums/{album_id}/photos/')
        self.assertEqual(photos.status_code, 200)
        self.assertEqual(photos.data['results'][0]['caption'], 'At the summit')
        self.assertTrue(photos.data['results'][0]['url'].startswith('http://testserver/api/albums/media/'))
        media_path = urlsplit(photos.data['results'][0]['url']).path
        self.client.force_authenticate(user=None)
        media = self.client.get(media_path)
        self.assertEqual(media.status_code, 200)
        self.assertEqual(media['Content-Type'], 'image/jpeg')
        self.assertTrue(b''.join(media.streaming_content))
        media.close()

    def test_rejects_invalid_album_color(self):
        response = self.client.post('/api/albums/', {
            'title': 'Unsafe color', 'color': 'red; background:url(x)',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_jpg_mpo_photo_is_saved_as_jpeg(self):
        album = self.client.post('/api/albums/', {'title': 'Camera photos'}, format='json')
        self.assertEqual(album.status_code, 201)
        buffer = io.BytesIO()
        Image.new('RGB', (12, 12), 'red').save(
            buffer,
            'MPO',
            save_all=True,
            append_images=[Image.new('RGB', (12, 12), 'blue')],
        )

        uploaded = self.client.post(
            f"/api/albums/{album.data['id']}/photos/upload/",
            {'photo': SimpleUploadedFile('camera.jpg', buffer.getvalue(), content_type='image/jpeg')},
            format='multipart',
        )

        self.assertEqual(uploaded.status_code, 201)
        asset = PhotoAsset.objects.get(pk=uploaded.data['asset_id'])
        self.assertEqual(asset.content_type, 'image/jpeg')
