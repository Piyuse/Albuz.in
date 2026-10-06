import hashlib
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .crypto import encrypt_json
from .google_oauth import build_google_flow
from .models import GoogleDriveConnection, GoogleOAuthState
from django.shortcuts import get_object_or_404

from rest_framework.exceptions import PermissionDenied, ValidationError
from .crypto import decrypt_json, encrypt_json

from oauthlib.oauth2 import OAuth2Error
from requests.exceptions import RequestException

GOOGLE_OAUTH_COOKIE = "google_oauth_browser"
GOOGLE_OAUTH_TTL_SECONDS = 600


def hash_oauth_value(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GoogleConnectStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        state = secrets.token_urlsafe(32)
        browser_nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)

        flow = build_google_flow(
            state=state,
            code_verifier=code_verifier,
        )

        authorization_url, returned_state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )

        expires_at = timezone.now() + timedelta(
            seconds=GOOGLE_OAUTH_TTL_SECONDS
        )

        GoogleOAuthState.objects.create(
            state_hash=hash_oauth_value(returned_state),
            user=request.user,
            browser_nonce_hash=hash_oauth_value(browser_nonce),
            code_verifier_encrypted=encrypt_json({
                "code_verifier": code_verifier,
            }),
            expires_at=expires_at,
        )

        response = Response({
            "authorization_url": authorization_url,
            "expires_at": expires_at,
        })

        response.set_cookie(
            key=GOOGLE_OAUTH_COOKIE,
            value=browser_nonce,
            max_age=GOOGLE_OAUTH_TTL_SECONDS,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            path="/api/integrations/google/",
        )

        response["Cache-Control"] = "no-store"
        return response
    
class GoogleCallbackView(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    
    def get(self,request):
        state=request.query_params.get('state',"")
        browser_nonce=request.COOKIES.get(GOOGLE_OAUTH_COOKIE,"")
        
        if not state or not browser_nonce:
            raise ValidationError({"detail": "Start a new google connection in the same browser."})

        
        with transaction.atomic():
            attempt=get_object_or_404(GoogleOAuthState.objects.select_for_update(),state_hash=hash_oauth_value(state),user=request.user,used_at__isnull=True,expires_at__gt=timezone.now())
            
            if attempt.expires_at <= timezone.now():
                raise ValidationError({
                    "detail":"The connection request has expired."
                })
            if not secrets.compare_digest(attempt.browser_nonce_hash,hash_oauth_value(browser_nonce)):
                raise PermissionDenied("Invalid browser nonce.")
            
            attempt.used_at=timezone.now()
            attempt.save(update_fields=["used_at"])
            
            user_id=attempt.user_id
            verifier_encrypted=attempt.code_verifier_encrypted
            
        self.clear_oauth_cookie=True
        code=request.query_params.get('code')
        
        if request.query_params.get('error') or not code:
            raise ValidationError({"detail": "Google autherisation was not completed"})
        
        verifier_data=decrypt_json(verifier_encrypted)
        
        flow=build_google_flow(
            state=state,
            code_verifier=verifier_data['code_verifier']
        )
        
        try:
            flow.fetch_token(code=code,timeout=60)
            credentials=flow.credentials
        except(OAuth2Error,RequestException,ValueError,Warning):
            return Response({"detail": "Google autherisation was not completed"},status=502)
        
        
        granted_scopes=(
            credentials.granted_scopes
            if credentials.granted_scopes is not None
            else credentials.scopes
        )
        
        if not set(settings.GOOGLE_DRIVE_SCOPES).issubset(set(granted_scopes or [])):
            raise PermissionDenied({"detail": "Google Drive read permission was not granted."})
        
        if not credentials.refresh_token:
            raise ValidationError({"detail": "Google did not return a refresh token."})
        
        credentials_data = json.loads(credentials.to_json())

        GoogleDriveConnection.objects.update_or_create(
            user_id=user_id,
            defaults={
                "credentials_encrypted": encrypt_json(credentials_data),
            },
        )

        return Response({"connected": True})

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request, response, *args, **kwargs
        )

        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"

        if getattr(self, "clear_oauth_cookie", False):
            response.delete_cookie(
                GOOGLE_OAUTH_COOKIE,
                path="/api/integrations/google/",
                samesite="Lax",
            )

        return response