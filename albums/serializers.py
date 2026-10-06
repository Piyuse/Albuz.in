from wsgiref.validate import validator

from rest_framework import serializers
from .models import Album,AlbumPhoto

class AlbumSerializer(serializers.ModelSerializer):
    class Meta:
        model = Album
        fields = ['id', 'owner', 'title', 'description', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']
        
class PhotoUploadSerializer(serializers.Serializer):
    photo = serializers.ImageField(write_only=True)
    
    caption = serializers.CharField(max_length=500, default="", allow_blank=True)
    
    def validate_photo(self,photo):
        max_size=10*1024*1024
        
        if photo.size>max_size:
            raise serializers.ValidationError("Photo size exceeds the maximum limit of 10MB.")
        
        allowed_formats={'JPEG','PNG','GIF','WEBP'}
        if photo.image.format not in allowed_formats:
            raise serializers.ValidationError(f"Unsupported photo format. Allowed formats: {', '.join(allowed_formats)}.")
        
        width, height = photo.image.size
        if width*height>20_000_000:
            raise serializers.ValidationError("Photo dimensions exceed the maximum limit of 20 million pixels.")    
        
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
        if not obj.asset.file:
            return None
        return obj.asset.file.url
    
class PhotoCopySerializer(serializers.Serializer):
    source_album_id = serializers.UUIDField()
    photo_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False,max_length=100 )
    
    def validate_photo_ids(self, photo_ids):
        if len(photo_ids) != len(set(photo_ids)):
            raise serializers.ValidationError("Duplicate photo IDs are not allowed.")
        return photo_ids
    
class BulkPhotoUploadSerializer(serializers.Serializer):
    photos = serializers.ListField(child=serializers.FileField(), allow_empty=False, max_length=100,write_only=True)
    caption= serializers.CharField(max_length=500, default="", allow_blank=True)
    
    def validate_photos(self, photos):
        total_size = sum(photo.size for photo in photos)
        if total_size > 100 * 1024 * 1024:
            raise serializers.ValidationError("Total size of all photos exceeds the maximum limit of 100MB.")
        
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
    destination_album_id=serializers.UUIDField  
    
    photo_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False,max_length=100 )
    
    def validate_photo_ids(self, photo_ids):
        if len(photo_ids) != len(set(photo_ids)):
            raise serializers.ValidationError("Duplicate photo IDs are not allowed.")
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