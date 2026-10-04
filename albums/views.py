from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .serializers import AlbumSerializer, PhotoUploadSerializer, AlbumPhotoSerializer,PhotoCopySerializer
from .models import Album, PhotoAsset, AlbumPhoto
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser
from django.shortcuts import get_object_or_404
import uuid
from django.db import transaction
import logging
from rest_framework.response import Response
from django.db.models import Max
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.exceptions import ValidationError
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

class AlbumPhotoPagination(PageNumberPagination):
    page_size = 50


class AlbumPhotoListView(generics.ListAPIView):
    serializer_class = AlbumPhotoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AlbumPhotoPagination
    
    def get_queryset(self):
        album = get_object_or_404(Album, pk=self.kwargs['album_id'], owner=self.request.user)
        return (
            AlbumPhoto.objects.filter(album=album,asset__isnull=False)
            .select_related('asset')
            .order_by('position', 'id')
        )
        
class PhotoCopyView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes =[JSONParser]
    
    def post(self, request, album_id):
        serializer=PhotoCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        source_id = serializer.validated_data['source_album_id']
        photo_ids = serializer.validated_data['photo_ids']
        
        if source_id == album_id:
            return Response({"detail": "Source and destination albums cannot be the same."}, status=400)

        
        with transaction.atomic():
            destination=get_object_or_404(Album.objects.select_for_update(), pk=album_id, owner=request.user)
            source=get_object_or_404(Album.objects.select_for_update(), pk=source_id, owner=request.user)
            selected=AlbumPhoto.objects.filter(album=source, id__in=photo_ids).select_related('asset')
            if len(selected) != len(photo_ids):
                raise ValidationError({"photo_ids": ["One or more photo IDs do not exist in the source album."]})
            
            existing_assests=set(destination.photos.values_list('asset_id', flat=True))
            last=destination.photos.aggregate(last=Max('position'))['last']
            position=(0 if last is None else last+1)
            
            copied_ids=[]
            skipped=0
            
            
            for photo in selected:
                if photo.asset_id in existing_assests:
                    skipped+=1
                    continue
                
                copy=AlbumPhoto.objects.create(
                    album=destination,
                    asset_id=photo.asset_id,
                    caption=photo.caption,
                    position=position
                )
                
                copied_ids.append(str(copy.pk))
                existing_assests.add(photo.asset_id)
                position+=1
                
            return Response({
                "copied": len(copied_ids),
                "skipped": skipped,
                "photo_ids": copied_ids
            }, status=201  if copied_ids else 200)