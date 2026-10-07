import io
import re

from django.core.files.uploadedfile import InMemoryUploadedFile
from googleapiclient.http import MediaIoBaseDownload
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from albums.serializers import PhotoUploadSerializer

from albums.constants import MAX_PHOTO_BYTES

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class LimitedPhotoBuffer(io.BytesIO):
    """Prevent downloaded images from exceeding the size limit."""

    def write(self, data):
        if self.tell() + len(data) > MAX_PHOTO_BYTES:
            raise ValidationError({
                "photo": "The downloaded image exceeds 10 MB."
            })

        return super().write(data)


def set_resource_keys(api_request, folder, file_id, resource_key):
    """Attach resource keys required for some shared Drive links."""

    keys = []

    if folder["resource_key"]:
        keys.append(
            f'{folder["folder_id"]}/{folder["resource_key"]}'
        )

    if resource_key:
        keys.append(f"{file_id}/{resource_key}")

    if keys:
        api_request.headers["X-Goog-Drive-Resource-Keys"] = (
            ",".join(keys)
        )

    return api_request


def download_drive_photo(
    service,
    folder,
    file_id,
    resource_key="",
):
    """
    Download and validate one photo from Google Drive.

    service: Authenticated client from get_drive_service().
    folder: Validated folder data from DriveFolderListSerializer.
    file_id: Google Drive file ID.
    resource_key: Optional resourceKey from the file-list response.

    The caller must close the returned photo when finished.
    """

    # Validate values before using them in API requests or headers.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", file_id):
        raise ValidationError({
            "file_id": "Invalid Google file ID."
        })

    if resource_key and not re.fullmatch(
        r"[A-Za-z0-9_-]{1,256}", resource_key
    ):
        raise ValidationError({
            "resource_key": "Invalid resource key."
        })

    # Read metadata and permissions before downloading.
    metadata_request = service.files().get(
        fileId=file_id,
        supportsAllDrives=True,
        fields=(
            "id,name,mimeType,size,parents,trashed,"
            "resourceKey,capabilities(canDownload)"
        ),
    )

    metadata = set_resource_keys(
        metadata_request,
        folder,
        file_id,
        resource_key,
    ).execute()

    if metadata.get("trashed"):
        raise ValidationError({
            "file_id": "This file was deleted."
        })

    if folder["folder_id"] not in metadata.get("parents", []):
        raise ValidationError({
            "file_id": (
                "This photo is not directly inside the folder."
            )
        })

    can_download = metadata.get("capabilities", {}).get(
        "canDownload", False
    )

    if not can_download:
        raise PermissionDenied(
            "Google does not allow downloading this photo."
        )

    mime_type = metadata.get("mimeType")

    if mime_type not in IMAGE_EXTENSIONS:
        raise ValidationError({
            "photo": (
                "Only JPEG, PNG, and WebP images are supported."
            )
        })

    if int(metadata.get("size", 0)) > MAX_PHOTO_BYTES:
        raise ValidationError({
            "photo": "The selected image exceeds 10 MB."
        })

    resource_key = metadata.get("resourceKey") or resource_key

    # Create a request for the actual file bytes.
    download_request = service.files().get_media(
        fileId=file_id,
        supportsAllDrives=True,
    )

    set_resource_keys(
        download_request,
        folder,
        file_id,
        resource_key,
    )

    buffer = LimitedPhotoBuffer()

    try:
        # Download into memory in 1 MB chunks.
        downloader = MediaIoBaseDownload(
            buffer,
            download_request,
            chunksize=1024 * 1024,
        )

        done = False

        while not done:
            _, done = downloader.next_chunk(num_retries=2)

        downloaded_size = buffer.tell()
        buffer.seek(0)

        # Wrap the bytes as a Django uploaded file.
        photo = InMemoryUploadedFile(
            file=buffer,
            field_name="photo",
            name=f"drive-photo{IMAGE_EXTENSIONS[mime_type]}",
            content_type=mime_type,
            size=downloaded_size,
            charset=None,
        )

        # Reuse the validation from manual photo uploads.
        serializer = PhotoUploadSerializer(data={
            "photo": photo,
            "caption": "",
        })
        serializer.is_valid(raise_exception=True)

        validated_photo = serializer.validated_data["photo"]

        if validated_photo.content_type != mime_type:
            raise ValidationError({
                "photo": (
                    "The image contents do not match "
                    "the file type reported by Google."
                )
            })

        # Reset the pointer so a later S3 upload reads from the start.
        validated_photo.seek(0)

        return {
            "photo": validated_photo,
            "filename": metadata["name"][:255],
            "width": validated_photo.image.width,
            "height": validated_photo.image.height,
        }

    except Exception:
        # Release the buffer if downloading or validation fails.
        buffer.close()
        raise