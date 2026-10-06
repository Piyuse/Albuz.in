from django.db import models
from django.conf import settings

# Create your models here.
class GoogleDriveConnection(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='google_drive_connection')
    credentials_encrypted=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    
class GoogleOAuthState(models.Model):
    state_hash=models.CharField(max_length=64,primary_key=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='google_oauth_states')
    browser_nonce_hash=models.CharField(max_length=64)
    code_verifier_encrypted=models.TextField()
    
    expires_at=models.DateTimeField()
    used_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    