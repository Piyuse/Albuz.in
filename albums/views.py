from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Album, PhotoAsset, AlbumPhoto,AlbumShare
from .serializers import AlbumSerializer, PhotoUploadSerializer,PhotoReorderSerializer,AlbumPhotoSerializer,PhotoCopySerializer,BulkPhotoUploadSerializer,SharedPhotoCopySerializer,ShareCreateSerializer,AlbumPhotoEditSerializer
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
from rest_framework.exceptions import PermissionDenied, ValidationError
import secrets
from django.utils import timezone
from django.urls import reverse
import hashlib
# Create your views here.
logger = logging.getLogger(__name__)

def hash_share_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

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
            
class BulkPhotoUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request, album_id):
        get_object_or_404(Album, pk=album_id, owner=request.user)
        serializer = BulkPhotoUploadSerializer(data={
            'photos': request.FILES.getlist('photos'),
            'caption': request.data.get('caption', '')
        })
        serializer.is_valid(raise_exception=True)

        photos = serializer.validated_data['photos']
        caption = serializer.validated_data['caption']
        formats = {
                                "JPEG": ("jpg", "image/jpeg"),
                                "PNG": ("png", "image/png"),
                                "WEBP": ("webp", "image/webp"),
                            }
        

        uploaded_files = []
        skipped_photos = 0
        total_size = sum(photo.size for photo in photos)

        if total_size > 100 * 1024 * 1024:
            return Response({"detail": "Total size of all photos exceeds the maximum limit of 100MB."}, status=400)

        with transaction.atomic():
            album = get_object_or_404(Album.objects.select_for_update(), pk=album_id, owner=request.user)
            last_position = album.photos.aggregate(last=Max('position'))['last']
            position = (0 if last_position is None else last_position + 1)

            for photo in photos:
                try:
                    width, height = photo.image.size
                   

                    extension, content_type = formats[photo.image.format]
                    asset = PhotoAsset(
                        filename=photo.name,
                        content_type=content_type,
                        size=photo.size,
                        width=width,
                        height=height
                    )

                    photo.seek(0)
                    asset.file.save(
                        f"{uuid.uuid4().hex}.{extension}",
                        photo,
                        save=False,
                    )
                    asset.save()

                    AlbumPhoto.objects.create(
                        album=album,
                        asset=asset,
                        caption=caption,
                        position=position
                    )
                    uploaded_files.append(str(asset.id))
                    position += 1

                except Exception as e:
                    logger.error(f"Failed to upload photo {photo.name}: {str(e)}")
                    skipped_photos += 1

        return Response({
            "uploaded": len(uploaded_files),
            "skipped": skipped_photos,
            "photo_ids": uploaded_files
        }, status=201 if uploaded_files else 200)
        
class ShareCreateView(APIView):
    permission_classes =[IsAuthenticated]
    parser_classes=[JSONParser]
    
    def post(self, request, album_id):
        album=get_object_or_404(Album, pk=album_id, owner=request.user)
        serializer=ShareCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token=secrets.token_urlsafe(32)
        share=AlbumShare.objects.create(
            album=album,
            token_hash=token,
            can_copy=serializer.validated_data['can_copy'],
            expires_at=timezone.now() + timezone.timedelta(hours=serializer.validated_data['expires_in_hours'])
        )
        url=request.build_absolute_uri(reverse('shared-album-photos', kwargs={'token': token}))
        response=Response({
            "id": str(share.pk),
            "url": url,
            "can_copy": share.can_copy,
            "expires_at": share.expires_at,
        },status=201)
        
        response["Cache-Control"]="no-store"
        return response
    
class SharedAlbumPhotoListView(generics.ListAPIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    serializer_class=AlbumPhotoSerializer
    pagination_class=AlbumPhotoPagination
     
    def get_queryset(self):
        self.share=get_object_or_404(AlbumShare.objects.select_related('album'), token_hash=self.kwargs['token'], revoked_at__isnull=True, expires_at__gt=timezone.now())
        return (
            AlbumPhoto.objects.filter(album=self.share.album, asset__isnull=False)
            .select_related('asset')
            .order_by('position', 'id')
        )
    def list(self,request,*args,**kwargs):
        response=super().list(request,*args,**kwargs)
        
        response.data["album"]= {
            "id":str(self.share.album_id),
            "title":self.share.album.title
        }
        response.data["can-copy"] =self.share.can_copy
        response["Cache-Control"]="no=store"
        
        return response
    
class ShareRevokeView(APIView):
    permission_classes=[IsAuthenticated]
    
    def delete(self,request,album_id,share_id):
        share=get_object_or_404(AlbumShare,pk=share_id,album_id=album_id,album__owner=request.user)
        if share.revoked_at is None:
            share.revoked_at=timezone.now()
            share.save(update_fields=["revoked_at"])
            
        return Response(status=204)
    
class SharedPhotoCopyView(generics.ListAPIView):
    permission_classes=[AllowAny]
    parser_classes=[JSONParser]
    
    def post(self,request,token):
        serializer=SharedPhotoCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        destination_id=serializer.validated_data['destination_album_id']
        photo_ids=serializer.validated_data['photo_ids']
        
        with transaction.atomic():
            share=get_object_or_404(AlbumShare.objects.select_for_update(),token_hash=hash_share_token(token),revoked_at__isnull=True,expires_at__gt=timezone.now())
            
            if not share.can_copy:
                raise PermissionDenied("This share does not allow copying.")
            
            destination=get_object_or_404(Album.objects.select_for_update(),pk=destination_id,owner=request.user)
            
            if share.expires_at<timezone.now():
                raise PermissionDenied("This share has expired.")
            
            if share.album_id==destination_id:
                raise PermissionDenied("Source and destination albums cannot be the same.")
            
            selected=AlbumPhoto.objects.filter(album_id=share.album,pk__in=photo_ids,asset__isnull=False).order_by('position','id')
            
            if len(selected)!=len(photo_ids):
                raise ValidationError({"photo_ids": ["One or more photo IDs do not exist in the source album."]})
            
            asset_ids = {photo.asset_id for photo in selected}
            
            existing_assets=set(destination.photos.filter(asset_id__in=asset_ids).values_list('asset_id', flat=True))
             
            last=destination.photos.aggregate(last=Max('position'))['last']
            
            position=(0 if last is None else last+1)
            copied_ids=[]
            skipped=0
            for photo in selected:
                if photo.asset_id in existing_assets:
                    skipped+=1
                    continue
                
                copy=AlbumPhoto.objects.create(
                    album=destination,
                    asset_id=photo.asset_id,
                    caption=photo.caption,
                    position=position
                )
                
                copied_ids.append(str(copy.pk))
                existing_assets.add(photo.asset_id)
                position+=1
                
            return Response({
                "destination_album_id": str(destination_id),
                "copied": len(copied_ids),
                "skipped": skipped,
                "photo_ids": copied_ids
            }, status=201  if copied_ids else 200)
            
            
class AlbumDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AlbumSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    lookup_url_kwarg = "album_id"

    http_method_names = [
        "get",
        "patch",
        "delete",
        "head",
        "options",
    ]

    def get_queryset(self):
        return Album.objects.filter(
            owner=self.request.user,
        )

    def perform_destroy(self, instance):
        with transaction.atomic():
            album = get_object_or_404(
                self.get_queryset().select_for_update(),
                pk=instance.pk,
            )

            album.delete()
    
class AlbumPhotoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class=AlbumPhotoEditSerializer
    permission_classes=[IsAuthenticated]
    parser_classes=[JSONParser]
    
    
    lookup_url_kwarg='photo_id'
    http_method_names=['get','patch','head','options','delete']
    def get_queryset(self):
        return AlbumPhoto.objects.filter(
            album_id=self.kwargs['album_id'],
            album__owner=self.request.user
        )
    def perform_destroy(self, instance):
        with transaction.atomic():
                get_object_or_404(
                Album.objects.select_for_update(),
                pk=instance.album_id,
                owner=self.request.user,
            )

        AlbumPhoto.objects.filter(
                pk=instance.pk,
                album_id=instance.album_id,
            ).delete()
        
class PhotoReorderView(APIView):
    permission_classes=[IsAuthenticated]
    parser_classes=[JSONParser]
    
    def post(self,request,album_id):
        serializer=PhotoReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        photo_ids=serializer.validated_data['photo_ids']
        
        with transaction.atomic():
            album = get_object_or_404(Album, pk=album_id, owner=request.user)
            photos_by_id = {photo.pk: photo for photo in album.photos.filter(asset__isnull=False).only('id','position')}
            
            if(set(photo_ids)!=set(photos_by_id)):
                raise ValidationError({"photo_ids": ["One or more photo IDs do not exist in the album."]})
            ordered_photos=[]
            
            for position,photo_id in enumerate(photo_ids):
                photo=photos_by_id[photo_id]
                photo.position=position
                ordered_photos.append(photo)
                
            AlbumPhoto.objects.bulk_update(ordered_photos, ['position'], batch_size=100)

            return Response(
                {
                    "album_id": str(album.pk),
                    "updated": len(ordered_photos),
                    "photo_ids": [str(photo_id) for photo_id in photo_ids],
                }
            )