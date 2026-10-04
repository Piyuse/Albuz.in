from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .serializers import AlbumSerializer, PhotoUploadSerializer
from .models import Album, PhotoAsset, AlbumPhoto
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser
from django.shortcuts import get_object_or_404
import uuid
from django.db import transaction
import logging
from rest_framework.response import Response
from django.db.models import Max
# Create your views here.
logger = logging.getLogger(__name__)

class AlbumListCreateView(generics.ListCreateAPIView):
    serializer_class = AlbumSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Album.objects.filter(owner=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
        
class PhotoUploadView(APIView):
    permission_classes = [IsAuthenticated] 
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, album_id):
        get_object_or_404(Album,pk=album_id,owner=request.user)
        serializer = PhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        photo = serializer.validated_data['photo']
        caption = serializer.validated_data['caption']
        
        width, height = photo.image.size
        
        formats={
            "JPEG": ("jpg", "image/jpeg"),
            "PNG": ("png", "image/png"),
            "WEBP": ("webp", "image/webp"),
            
        }
        
        extension, content_type = formats[photo.image.format]
        asset = PhotoAsset(
            filename=photo.name,
            content_type=content_type,
            size=photo.size,
            width=width,
            height=height
        )
        
        stored_name=None
        
        try:
            with transaction.atomic():
                album=get_object_or_404(Album.objects.select_for_update(),pk=album_id,owner=request.user)
                last_position=album.photos.aggregate(last=Max('position'))['last']
                position=(0 if last_position is None else last_position+1)
                photo.seek(0)
                asset.file.save(
                    f"{uuid.uuid4().hex}.{extension}",
                    photo,
                    save=False,
                )
                stored_name=asset.file.name
                asset.save()
                entry=AlbumPhoto.objects.create(
                    album=album,
                    asset=asset,
                    caption=caption,
                    position=position
                )
                
        except Exception as e:
            if stored_name:
                try:
                    asset.file.storage.delete(stored_name)
                except Exception:
                    logger.error(f"Failed to delete stored photo {stored_name} after transaction failure.")
            raise e

        
        return Response({
            "id": entry.id,
            "album_id": album_id,
            "asset_id": asset.id,
            "caption": caption,
            "position": position,
            "created_at": entry.created_at
        }, status=201)