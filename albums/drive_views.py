import logging

import httplib2
from botocore.exceptions import BotoCoreError, ClientError
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.errors import HttpError
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.drive_downloads import (
    IMAGE_EXTENSIONS,
    download_drive_photo,
)
from integrations.google_drive import get_drive_service
from integrations.serializers import DriveImportSerializer

from .models import Album, AlbumPhoto, PhotoAsset


logger = logging.getLogger(__name__)

MAX_BATCH_BYTES = 50 * 1024 * 1024


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class DrivePhotoImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, album_id):
        serializer = DriveImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Reject requests for someone else's album before downloading.
        get_object_or_404(
            Album,
            pk=album_id,
            owner=request.user,
        )

        service = None
        prepared_photos = []
        uploaded_files = []
        imported_ids = []
        committed = False

        try:
            service = get_drive_service(request.user)
            total_bytes = 0

            # Phase 1: Download and validate every selected photo.
            for selection in data["photos"]:
                downloaded = download_drive_photo(
                    service=service,
                    folder=data["folder_link"],
                    file_id=selection["file_id"],
                    resource_key=selection["resource_key"],
                )

                downloaded["caption"] = selection["caption"]
                prepared_photos.append(downloaded)

                total_bytes += downloaded["photo"].size

                if total_bytes > MAX_BATCH_BYTES:
                    raise ValidationError({
                        "photos": (
                            "The selected photos exceed "
                            "the 50 MB batch limit."
                        )
                    })

            # Phase 2: Upload validated files to the configured storage.
            assets = []

            for item in prepared_photos:
                photo = item["photo"]

                asset = PhotoAsset(
                    filename=item["filename"],
                    content_type=photo.content_type,
                    size=photo.size,
                    width=item["width"],
                    height=item["height"],
                )

                extension = IMAGE_EXTENSIONS[photo.content_type]

                # Use the PhotoAsset FileField's storage and upload path.
                file_field = PhotoAsset._meta.get_field("file")
                storage = file_field.storage

                object_name = file_field.generate_filename(
                    asset,
                    f"{asset.id.hex}{extension}",
                )

                # Track the intended key before starting the upload.
                uploaded_files.append((storage, object_name))

                photo.seek(0)
                saved_name = storage.save(object_name, photo)

                # Storage can adjust the filename if necessary.
                uploaded_files[-1] = (storage, saved_name)

                # The file is already uploaded; assign its stored key.
                asset.file.name = saved_name
                assets.append(asset)

            # Phase 3: Save all database records together.
            with transaction.atomic(durable=True):
                album = get_object_or_404(
                    Album.objects.select_for_update(),
                    pk=album_id,
                    owner=request.user,
                )

                last_position = album.photos.aggregate(
                    last=Max("position")
                )["last"]

                next_position = (
                    last_position + 1
                    if last_position is not None
                    else 0
                )

                for asset, item in zip(assets, prepared_photos):
                    asset.save(force_insert=True)

                    album_photo = AlbumPhoto.objects.create(
                        album=album,
                        asset=asset,
                        caption=item["caption"],
                        position=next_position,
                    )

                    imported_ids.append(str(album_photo.id))
                    next_position += 1

            committed = True

        except RefreshError:
            raise ValidationError({
                "detail": "Reconnect your Google Drive account."
            })

        except HttpError as exc:
            google_status = int(exc.resp.status)

            if google_status == 400:
                raise ValidationError({
                    "detail": "Google rejected the selected file request."
                })

            if google_status == 401:
                raise ValidationError({
                    "detail": "Reconnect your Google Drive account."
                })

            if google_status == 403:
                raise PermissionDenied(
                    "Google denied access. Check file permissions, "
                    "Drive API configuration, and API quota."
                )

            if google_status == 404:
                raise NotFound(
                    "A selected file was not found or is unavailable "
                    "to your connected Google account."
                )

            return Response(
                {"detail": "Google Drive is temporarily unavailable."},
                status=502,
            )

        except (TransportError, httplib2.HttpLib2Error, OSError):
            return Response(
                {"detail": "Could not download the selected photos."},
                status=502,
            )

        except (BotoCoreError, ClientError):
            logger.exception("S3 upload failed during Drive import")

            return Response(
                {"detail": "Could not save the photos to S3."},
                status=502,
            )

        finally:
            # A database rollback cannot undo an S3 upload.
            if not committed:
                for storage, object_name in uploaded_files:
                    try:
                        storage.delete(object_name)
                    except Exception:
                        logger.exception(
                            "Could not clean up imported object: %s",
                            object_name,
                        )

            for item in prepared_photos:
                item["photo"].close()

            if service is not None:
                try:
                    service.close()
                except Exception:
                    logger.warning(
                        "Could not close the Google Drive client"
                    )

        return Response(
            {
                "album_id": str(album_id),
                "imported": len(imported_ids),
                "photo_ids": imported_ids,
            },
            status=201,
        )