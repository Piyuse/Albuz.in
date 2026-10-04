from rest_framework import serializers
from .models import Album

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
        