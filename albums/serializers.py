from rest_framework import serializers
from .models import Album

class AlbumSerializer(serializers.ModelSerializer):
    class Meta:
        model = Album
        fields = ['id', 'owner', 'title', 'description', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']
        