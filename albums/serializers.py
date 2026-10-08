import io
import re
from wsgiref.validate import validator

from rest_framework import serializers

from .constants import MAX_BULK_UPLOAD_BYTES, MAX_PHOTO_BYTES, MAX_PHOTO_MIB, MAX_PHOTO_PIXELS, PHOTO_FORMATS
from .models import Album,AlbumPhoto
from .media import photo_url


class AlbumSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField()
    photo_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Album
        fields = ['id', 'owner', 'title', 'description', 'category', 'color', 'created_at', 'cover_url', 'photo_count']
        read_only_fields = ['id', 'owner', 'created_at', 'cover_url', 'photo_count']

    def validate_color(self, value):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise serializers.ValidationError('Use a six-digit hex color.')
        return value

    def get_cover_url(self, obj):
        active_photos = getattr(obj, 'active_photos', None)
        if active_photos is not None:
            first = active_photos[0] if active_photos else None
        else:
            first = obj.photos.filter(is_deleted=False).select_related('asset').first()
        return photo_url(first.asset, self.context.get('request')) if first else None
        
class PhotoUploadSerializer(serializers.Serializer):
    photo = serializers.ImageField(write_only=True)
    
    caption = serializers.CharField(max_length=255, default="", allow_blank=True)
    
    def validate_photo(self,photo):
        if photo.size > MAX_PHOTO_BYTES:
            raise serializers.ValidationError(f"Photo size exceeds the maximum limit of {MAX_PHOTO_MIB} MB.")
        
        if photo.image.format not in PHOTO_FORMATS:
            raise serializers.ValidationError(
                f"Unsupported photo format ({photo.image.format or 'unknown'}). "
                "Supported photos are JPG, PNG, and WebP."
            )
        
        width, height = photo.image.size
        if width * height > MAX_PHOTO_PIXELS:
            raise serializers.ValidationError("Photo dimensions exceed the maximum limit of 80 million pixels.")
        
        return photo
    

class AlbumPhotoSerializer(serializers.ModelSerializer):
    filename = serializers.CharField(source='asset.filename', read_only=True)
    width = serializers.IntegerField(source='asset.width', read_only=True)
    height = serializers.IntegerField(source='asset.height', read_only=True)
    url = serializers.SerializerMethodField()
    
    class Meta:
        model = AlbumPhoto
        fields = ['id',  'caption', 'position', 'created_at', 'filename', 'width', 'height', 'url']
        read_only_fields = fields
        
    def get_url(self, obj):
        return photo_url(obj.asset, self.context.get('request'))
    
class PhotoCopySerializer(serializers.Serializer):
    source_album_id = serializers.UUIDField()
    photo_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False,max_length=100 )
    
    def validate_photo_ids(self, photo_ids):
        if len(photo_ids) != len(set(photo_ids)):
            raise serializers.ValidationError("Duplicate photo IDs are not allowed.")
        return photo_ids
    
class BulkPhotoUploadSerializer(serializers.Serializer):
    photos = serializers.ListField(child=serializers.FileField(), allow_empty=False, max_length=100,write_only=True)
    caption= serializers.CharField(max_length=255, default="", allow_blank=True)
    
    def validate_photos(self, photos):
        total_size = sum(photo.size for photo in photos)
        if total_size > MAX_BULK_UPLOAD_BYTES:
            raise serializers.ValidationError("Total size of all photos exceeds the 3 GB batch limit.")
        
        validator = PhotoUploadSerializer(
            data=[{'photo': photo} for photo in photos],
            many=True
        )
        
        validator.is_valid(raise_exception=True)
        return [
            item["photo"]
            for item in validator.validated_data
        ]
        
class ShareCreateSerializer(serializers.Serializer):
    can_copy = serializers.BooleanField(default=False)
    expires_in_hours = serializers.IntegerField(min_value=1, max_value=720, default=168)
    
class SharedPhotoCopySerializer(serializers.Serializer):
    destination_album_id = serializers.UUIDField(
        required=True,
    )

    photo_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100,
        required=True,
    )

    def validate_photo_ids(self, photo_ids):
        if len(photo_ids) != len(set(photo_ids)):
            raise serializers.ValidationError(
                "Duplicate photo IDs are not allowed."
            )

        return photo_ids

class AlbumPhotoEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlbumPhoto
        fields = ['id', 'caption' ]
        read_only_fields = ['id']
        
class PhotoReorderSerializer(serializers.Serializer):
    photo_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False,max_length=100 )
    
    def validate_photo_ids(self, photo_ids):
        if len(photo_ids) != len(set(photo_ids)):
            raise serializers.ValidationError("Duplicate photo IDs are not allowed.")
        return photo_ids
