import uuid

from django.db import models


# Create your models here.
class Album(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey('accounts.User',on_delete=models.CASCADE,related_name='albums')
    title=models.CharField(max_length=255)
    description=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
    
    