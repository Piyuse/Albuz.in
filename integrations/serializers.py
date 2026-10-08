
from rest_framework import serializers
import re
from urllib.parse import parse_qs, urlsplit

class DriveFolderListSerializer(serializers.Serializer):
    folder_link=serializers.URLField(max_length=2000)
    page_token=serializers.CharField(required=False,allow_blank=True,max_length=2000)
    album_id=serializers.UUIDField(required=False)
    
    def validate_folder_link(self,value):
        url=urlsplit(value)
        
        if url.scheme!='https' or url.netloc!='drive.google.com':
            raise serializers.ValidationError("Please provide a valid Google Drive folder link.")
        
        match = re.fullmatch(
            r"/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]{1,200})/?",
            url.path,
        )
        
        if not match:
            raise serializers.ValidationError("Please provide a valid Google Drive folder link.ttps://drive.google.com/drive/folders/FOLDER_ID")

        resource_key=parse_qs(url.query).get('resourcekey',[""])[0]
        
        if resource_key and not re.fullmatch(r"[A-Za-z0-9_-]{1,256}",resource_key):
            raise serializers.ValidationError("Invalid resource key.")
        
        return {
            "folder_id": match.group(1),
            "resource_key": resource_key,
        }
        
class DrivePhotoSelectionSerializer(serializers.Serializer):
    file_id = serializers.RegexField(
        regex=r"^[A-Za-z0-9_-]{1,200}$",
        max_length=200,
    )

    resource_key = serializers.RegexField(
        regex=r"^[A-Za-z0-9_-]{1,256}$",
        required=False,
        allow_blank=True,
        default="",
        max_length=256,
    )

    caption = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=255,
    )


class DriveImportSerializer(serializers.Serializer):
    folder_link = serializers.URLField(max_length=2000)

    photos = DrivePhotoSelectionSerializer(
        many=True,
        allow_empty=False,
        max_length=10,
    )

    def validate_folder_link(self, value):
        # Reuse the folder-link validation from the previous step.
        return DriveFolderListSerializer().validate_folder_link(value)

    def validate_photos(self, photos):
        file_ids = [photo["file_id"] for photo in photos]

        if len(file_ids) != len(set(file_ids)):
            raise serializers.ValidationError(
                "The same Google file cannot appear twice."
            )

        return photos
