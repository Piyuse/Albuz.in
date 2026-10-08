import re
from tempfile import SpooledTemporaryFile

from django.core.files.uploadedfile import UploadedFile
from googleapiclient.http import MediaIoBaseDownload
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from albums.serializers import PhotoUploadSerializer

from albums.constants import MAX_PHOTO_BYTES, MAX_PHOTO_MIB, PHOTO_FORMATS

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

DRIVE_MIME_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
}


class LimitedPhotoBuffer(SpooledTemporaryFile):
    """Spool large Drive downloads to disk while enforcing the file limit."""

    def __init__(self):
        super().__init__(max_size=8 * 1024 * 1024, mode="w+b")

    def write(self, data):
        if self.tell() + len(data) > MAX_PHOTO_BYTES:
            raise ValidationError({
                "photo": f"The downloaded image exceeds {MAX_PHOTO_MIB} MB."
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

    mime_type = DRIVE_MIME_ALIASES.get(
        metadata.get("mimeType"), metadata.get("mimeType")
    )

    if mime_type not in IMAGE_EXTENSIONS:
        raise ValidationError({
            "photo": (
                "Only JPG, PNG, and WebP images are supported."
            )
        })

    if int(metadata.get("size", 0)) > MAX_PHOTO_BYTES:
        raise ValidationError({
            "photo": f"The selected image exceeds {MAX_PHOTO_MIB} MB."
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
        # Download in 1 MB chunks; files larger than 8 MB spill to disk.
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

        # Wrap the disk-backed stream as a Django uploaded file.
        photo = UploadedFile(
            file=buffer,
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

        # Pillow has verified the bytes, so its detected type takes precedence
        # over Drive metadata. MPO has a primary JPEG image.
        extension, detected_mime_type = PHOTO_FORMATS[validated_photo.image.format]
        validated_photo.content_type = detected_mime_type
        validated_photo.name = f"drive-photo.{extension}"

        filename = metadata["name"][:255]
        if detected_mime_type != mime_type:
            stem = filename.rsplit(".", 1)[0] if "." in filename else filename
            filename = f"{stem[:250]}.{extension}"

        # Reset the pointer so a later S3 upload reads from the start.
        validated_photo.seek(0)

        return {
            "photo": validated_photo,
            "filename": filename,
            "width": validated_photo.image.width,
            "height": validated_photo.image.height,
        }

    except Exception:
        # Release the buffer if downloading or validation fails.
        buffer.close()
        raise
