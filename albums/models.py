import uuid

from django.db import models


# Create your models here.
class Album(models.Model):
    CATEGORY_CHOICES = [
        ('Travel', 'Travel'),
        ('Everyday', 'Everyday'),
        ('Together', 'Together'),
    ]
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey('accounts.User',on_delete=models.CASCADE,related_name='albums')
    title=models.CharField(max_length=255)
    description=models.TextField(blank=True)
    category=models.CharField(max_length=16, choices=CATEGORY_CHOICES, default='Everyday')
    color=models.CharField(max_length=7, default='#677a71')
    created_at=models.DateTimeField(auto_now_add=True)
    is_deleted=models.BooleanField(default=False, db_column='isdeleted')
    deleted_at=models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
    
class PhotoAsset(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    file=models.FileField(upload_to='photos/')
    filename=models.CharField(max_length=255)
    content_type=models.CharField(max_length=100)
    size=models.PositiveIntegerField()
    width=models.PositiveIntegerField()
    height=models.PositiveIntegerField()
    
    created_at=models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.filename
    
class AlbumPhoto(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    album=models.ForeignKey(Album,on_delete=models.CASCADE,related_name='photos')
    asset=models.ForeignKey(PhotoAsset,on_delete=models.PROTECT,related_name='placements')
    source_drive_file_id=models.CharField(max_length=200,null=True,blank=True)
    caption=models.CharField(max_length=255,blank=True)
    position=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    is_deleted=models.BooleanField(default=False, db_column='isdeleted')
    deleted_at=models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['position','id']
        constraints = [
            models.UniqueConstraint(fields=['album','asset'],name='unique_album_asset'),
            models.UniqueConstraint(fields=['album','source_drive_file_id'],name='unique_album_drive_file'),
        ]
    
    def __str__(self):
        return f"{self.album.title} - {self.asset.filename}"
    

class AlbumShare(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    album=models.ForeignKey(Album,on_delete=models.CASCADE,related_name='shares')
    token_hash=models.CharField(max_length=64,unique=True)
    can_copy=models.BooleanField(default=False)
    expires_at=models.DateTimeField()
    revoked_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    
class PendingPhotoDeletion(models.Model):
    file_name = models.CharField(
        max_length=512,
        unique=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
