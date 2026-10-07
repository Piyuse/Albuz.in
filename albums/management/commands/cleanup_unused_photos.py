from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from albums.models import (
    AlbumPhoto,
    PendingPhotoDeletion,
    PhotoAsset,
)


class Command(BaseCommand):
    help = "Clean up photo assets that no album references."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Apply cleanup. Without this flag, only preview.",
        )

        parser.add_argument(
            "--older-than-hours",
            type=int,
            default=24,
            help="Minimum asset age in hours. Default: 24.",
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum assets and queued files per run.",
        )

    def handle(self, *args, **options):
        hours = options["older_than_hours"]
        limit = options["limit"]

        if hours < 0:
            raise CommandError("--older-than-hours cannot be negative.")

        if not 1 <= limit <= 1000:
            raise CommandError("--limit must be between 1 and 1000.")

        cutoff = timezone.now() - timedelta(hours=hours)

        placements = AlbumPhoto.objects.filter(
            asset_id=OuterRef("pk"),
        )

        candidates = (
            PhotoAsset.objects
            .filter(created_at__lt=cutoff)
            .annotate(in_use=Exists(placements))
            .filter(in_use=False)
            .order_by("created_at", "id")
        )

        selected = list(
            candidates.values("id", "file")[:limit]
        )

        if not options["delete"]:
            for asset in selected:
                self.stdout.write(
                    f"Would remove unused asset: "
                    f"{asset['id']} | {asset['file']}"
                )

            pending_keys = (
                PendingPhotoDeletion.objects
                .values_list("file_name", flat=True)[:limit]
            )

            for file_name in pending_keys:
                self.stdout.write(
                    f"Would retry queued file deletion: {file_name}"
                )

            self.stdout.write(
                "Dry run complete. Nothing was changed."
            )
            return

        removed_assets = 0
        deleted_files = 0
        failures = 0

        # First remove unused asset records and queue their file keys.
        for asset in selected:
            try:
                if self.queue_unused_asset(asset["id"], cutoff):
                    removed_assets += 1

            except ProtectedError:
                # An album reference prevents deleting this asset.
                self.stdout.write(
                    f"Skipped referenced asset: {asset['id']}"
                )

            except Exception as exc:
                failures += 1
                self.stderr.write(
                    f"Could not queue asset {asset['id']}: {exc}"
                )

        # Process both newly queued files and previous failed deletions.
        pending_ids = list(
            PendingPhotoDeletion.objects
            .values_list("pk", flat=True)[:limit]
        )

        storage = PhotoAsset._meta.get_field("file").storage

        for deletion_id in pending_ids:
            try:
                if self.delete_queued_file(deletion_id, storage):
                    deleted_files += 1

            except Exception as exc:
                failures += 1
                self.stderr.write(
                    f"Queued deletion {deletion_id} failed: {exc}"
                )

        self.stdout.write(
            f"Removed unused asset records: {removed_assets}"
        )
        self.stdout.write(
            f"Deleted queued files: {deleted_files}"
        )
        self.stdout.write(
            "Remaining queued files: "
            f"{PendingPhotoDeletion.objects.count()}"
        )

        if failures:
            raise CommandError(
                f"{failures} cleanup operations failed. "
                "Queued file deletions remain available for retry."
            )

    def queue_unused_asset(self, asset_id, cutoff):
        with transaction.atomic(durable=True):
            asset = (
                PhotoAsset.objects
                .select_for_update()
                .filter(
                    pk=asset_id,
                    created_at__lt=cutoff,
                )
                .first()
            )

            if asset is None:
                return False

            # Recheck after acquiring the lock.
            if AlbumPhoto.objects.filter(asset_id=asset.pk).exists():
                return False

            if asset.file.name:
                PendingPhotoDeletion.objects.get_or_create(
                    file_name=asset.file.name,
                )

            asset.delete()

        return True

    def delete_queued_file(self, deletion_id, storage):
        with transaction.atomic(durable=True):
            deletion = (
                PendingPhotoDeletion.objects
                .select_for_update()
                .filter(pk=deletion_id)
                .first()
            )

            if deletion is None:
                return False

            # Protect a file if another asset record uses the same key.
            if PhotoAsset.objects.filter(
                file=deletion.file_name,
            ).exists():
                return False

            storage.delete(deletion.file_name)
            deletion.delete()

        return True