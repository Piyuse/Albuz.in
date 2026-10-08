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


def matches_stored_photo(photo, asset):
    """Compare a downloaded photo with a legacy album asset without loading either in RAM."""
    photo.seek(0)
    try:
        with asset.file.open("rb") as stored:
            while True:
                downloaded_chunk = photo.read(1024 * 1024)
                stored_chunk = stored.read(1024 * 1024)
                if downloaded_chunk != stored_chunk:
                    return False
                if not downloaded_chunk:
                    return True
    finally:
        photo.seek(0)


def restore_drive_photos(album, file_ids, next_position):
    """Re-add previously removed Drive placements without downloading them again."""
    restored_ids = []
    skipped = 0
    for placement in AlbumPhoto.objects.filter(album=album, source_drive_file_id__in=file_ids):
        if not placement.is_deleted:
            skipped += 1
            continue
        placement.is_deleted = False
        placement.deleted_at = None
        placement.position = next_position
        placement.save(update_fields=['is_deleted', 'deleted_at', 'position'])
        restored_ids.append(str(placement.pk))
        next_position += 1
    return restored_ids, skipped, next_position


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class DrivePhotoImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, album_id):
        serializer = DriveImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Reject requests for someone else's album before downloading.
        album = get_object_or_404(
            Album,
            pk=album_id,
            owner=request.user,
            is_deleted=False,
        )

        requested_ids = [photo["file_id"] for photo in data["photos"]]
        existing_ids = set(
            AlbumPhoto.objects.filter(
                album=album,
                is_deleted=False,
                source_drive_file_id__in=requested_ids,
            ).values_list("source_drive_file_id", flat=True)
        )
        skipped = len(existing_ids)
        deleted_ids = set(AlbumPhoto.objects.filter(
            album=album, is_deleted=True, source_drive_file_id__in=requested_ids,
        ).values_list('source_drive_file_id', flat=True))
        pending = [photo for photo in data["photos"] if photo["file_id"] not in existing_ids | deleted_ids]
        if not pending:
            restored_ids = []
            if deleted_ids:
                with transaction.atomic(durable=True):
                    album = get_object_or_404(Album.objects.select_for_update(), pk=album_id, owner=request.user, is_deleted=False)
                    last = album.photos.filter(is_deleted=False).aggregate(last=Max('position'))['last']
                    restored_ids, newly_skipped, _ = restore_drive_photos(album, deleted_ids, 0 if last is None else last + 1)
                    skipped += newly_skipped
            return Response({
                "album_id": str(album_id),
                "imported": len(restored_ids),
                "skipped": skipped,
                "photo_ids": restored_ids,
            }, status=201 if restored_ids else 200)

        service = None
        prepared_photos = []
        uploaded_files = []
        redundant_files = []
        imported_ids = []
        committed = False

        try:
            service = get_drive_service(request.user)
            # Process one photo at a time so an import never holds every
            # selected download in temporary storage at once.
            for selection in pending:
                downloaded = download_drive_photo(
                    service=service,
                    folder=data["folder_link"],
                    file_id=selection["file_id"],
                    resource_key=selection["resource_key"],
                )
                photo = downloaded["photo"]
                try:
                    legacy_photos = AlbumPhoto.objects.filter(
                        album=album,
                        is_deleted=False,
                        source_drive_file_id__isnull=True,
                        asset__size=photo.size,
                    ).select_related("asset")
                    legacy_match = next(
                        (placement for placement in legacy_photos if matches_stored_photo(photo, placement.asset)),
                        None,
                    )
                    if legacy_match is not None:
                        with transaction.atomic():
                            Album.objects.select_for_update().get(pk=album.pk, is_deleted=False)
                            already_recorded = AlbumPhoto.objects.filter(
                                album=album,
                                source_drive_file_id=selection["file_id"],
                            ).exists()
                            linked = 0 if already_recorded else AlbumPhoto.objects.filter(
                                pk=legacy_match.pk,
                                source_drive_file_id__isnull=True,
                            ).update(source_drive_file_id=selection["file_id"])
                        if already_recorded or linked:
                            skipped += 1
                            continue

                    asset = PhotoAsset(
                        filename=downloaded["filename"],
                        content_type=photo.content_type,
                        size=photo.size,
                        width=downloaded["width"],
                        height=downloaded["height"],
                    )

                    extension = IMAGE_EXTENSIONS[photo.content_type]
                    file_field = PhotoAsset._meta.get_field("file")
                    storage = file_field.storage
                    object_name = file_field.generate_filename(
                        asset,
                        f"{asset.id.hex}{extension}",
                    )

                    uploaded_files.append((storage, object_name))
                    photo.seek(0)
                    saved_name = storage.save(object_name, photo)
                    uploaded_files[-1] = (storage, saved_name)
                    asset.file.name = saved_name
                    prepared_photos.append((asset, selection["caption"], selection["file_id"]))
                finally:
                    photo.close()

            # Save all album records together after the files are stored.
            with transaction.atomic(durable=True):
                album = get_object_or_404(
                    Album.objects.select_for_update(),
                    pk=album_id,
                    owner=request.user,
                    is_deleted=False,
                )

                last_position = album.photos.filter(is_deleted=False).aggregate(
                    last=Max("position")
                )["last"]

                next_position = (
                    last_position + 1
                    if last_position is not None
                    else 0
                )

                restored_ids, newly_skipped, next_position = restore_drive_photos(album, deleted_ids, next_position)
                imported_ids.extend(restored_ids)
                skipped += newly_skipped

                existing_ids = set(
                    AlbumPhoto.objects.filter(
                        album=album,
                        source_drive_file_id__in=[item[2] for item in prepared_photos],
                    ).values_list("source_drive_file_id", flat=True)
                )

                for asset, caption, source_file_id in prepared_photos:
                    if source_file_id in existing_ids:
                        skipped += 1
                        redundant_files.append((asset.file.storage, asset.file.name))
                        continue

                    asset.save(force_insert=True)

                    album_photo = AlbumPhoto.objects.create(
                        album=album,
                        asset=asset,
                        source_drive_file_id=source_file_id,
                        caption=caption,
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
            cleanup_files = redundant_files if committed else uploaded_files
            for storage, object_name in cleanup_files:
                try:
                    storage.delete(object_name)
                except Exception:
                    logger.exception(
                        "Could not clean up imported object: %s",
                        object_name,
                    )

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
                "skipped": skipped,
                "photo_ids": imported_ids,
            },
            status=201 if imported_ids else 200,
        )
