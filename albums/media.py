from django.core import signing
from django.core.files.storage import FileSystemStorage
from django.urls import reverse


def photo_url(asset, request=None):
    if not asset or not asset.file:
        return None
    if isinstance(asset.file.storage, FileSystemStorage):
        token = signing.dumps(str(asset.pk), salt='album-photo')
        path = reverse('album-photo-media', kwargs={'token': token})
        return request.build_absolute_uri(path) if request else path
    return asset.file.url
