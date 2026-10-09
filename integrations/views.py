import hashlib
import json
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponseRedirect
from django.http import Http404
from django.db import transaction
from django.utils import timezone

import httplib2
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.google_drive import apply_resource_key, get_drive_service
from integrations.serializers import DriveFolderListSerializer
from albums.models import Album, AlbumPhoto

from .google_oauth import build_google_flow
from .models import GoogleDriveConnection, GoogleOAuthState
from django.shortcuts import get_object_or_404

from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from .crypto import decrypt_json, encrypt_json

from oauthlib.oauth2 import OAuth2Error
from requests.exceptions import RequestException

from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.errors import HttpError

GOOGLE_OAUTH_TTL_SECONDS = 600
logger = logging.getLogger(__name__)


class GoogleConnectSetupError(APIException):
    status_code = 503
    default_code = "google_connect_unavailable"


def hash_oauth_value(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def allowed_frontend_origins():
    configured = urlsplit(settings.FRONTEND_URL)
    origins = {urlunsplit((configured.scheme, configured.netloc, "", "", ""))}
    if configured.hostname in {"localhost", "127.0.0.1"}:
        alternate = "localhost" if configured.hostname == "127.0.0.1" else "127.0.0.1"
        if configured.port:
            alternate += f":{configured.port}"
        origins.add(urlunsplit((configured.scheme, alternate, "", "", "")))
    return origins


class GoogleConnectStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return_origin = request.data.get("return_origin") or request.headers.get("Origin") or settings.FRONTEND_URL
        if return_origin not in allowed_frontend_origins():
            raise ValidationError({
                "detail": "The application address is not an allowed Google connection return address."
            })

        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)

        try:
            flow = build_google_flow(
                state=state,
                code_verifier=code_verifier,
            )
            authorization_url, returned_state = flow.authorization_url(
                access_type="offline",
                prompt="consent",
            )
        except Exception:
            logger.exception("Google connection failed during authorization setup")
            raise GoogleConnectSetupError(
                "Google Drive authorization setup failed on the server."
            )

        expires_at = timezone.now() + timedelta(
            seconds=GOOGLE_OAUTH_TTL_SECONDS
        )

        try:
            encrypted_verifier = encrypt_json({
                "code_verifier": code_verifier,
                "return_origin": return_origin,
            })
        except Exception:
            logger.exception("Google connection failed while encrypting OAuth state")
            raise GoogleConnectSetupError(
                "Google Drive encryption setup failed on the server."
            )

        try:
            GoogleOAuthState.objects.create(
                state_hash=hash_oauth_value(returned_state),
                user=request.user,
                code_verifier_encrypted=encrypted_verifier,
                expires_at=expires_at,
            )
        except Exception:
            logger.exception("Google connection failed while saving OAuth state")
            raise GoogleConnectSetupError(
                "Google Drive could not save the connection attempt."
            )

        response = Response({
            "authorization_url": authorization_url,
            "expires_at": expires_at,
        })

        response["Cache-Control"] = "no-store"
        return response
    
class GoogleCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        self.oauth_return_url = settings.FRONTEND_URL
        state = request.query_params.get("state", "")

        if not state:
            self.oauth_error_reason = "expired"
            raise ValidationError({
                "detail": "Start a new Google connection."
            })

        # The one-time state binds the callback to a user and the stored PKCE verifier.
        # A browser cookie is unnecessary because Google may return to a different
        # loopback host from the one serving the frontend.
        with transaction.atomic():
            self.oauth_error_reason = "expired"
            attempt = get_object_or_404(
                GoogleOAuthState.objects.select_for_update(),
                state_hash=hash_oauth_value(state),
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )

            if attempt.expires_at <= timezone.now():
                raise ValidationError({
                    "detail": "This connection attempt expired."
                })

            verifier_data = decrypt_json(attempt.code_verifier_encrypted)
            return_origin = verifier_data.get("return_origin")
            if return_origin in allowed_frontend_origins():
                self.oauth_return_url = return_origin

            attempt.used_at = timezone.now()
            attempt.save(update_fields=["used_at"])

            user_id = attempt.user_id

        code = request.query_params.get("code")

        if request.query_params.get("error") or not code:
            self.oauth_error_reason = "denied"
            raise ValidationError({
                "detail": (
                    "Google authorization was not completed. "
                    "Start a new connection."
                )
            })

        flow = build_google_flow(
            state=state,
            code_verifier=verifier_data["code_verifier"],
        )

        try:
            self.oauth_error_reason = "exchange"
            flow.fetch_token(code=code, timeout=20)
            credentials = flow.credentials

        except (OAuth2Error, RequestException, ValueError, Warning):
            raise ValidationError({
                "detail": "Google authorization could not be completed. Start a new connection."
            })

        granted_scopes = credentials.granted_scopes

        if granted_scopes is None:
            granted_scopes = credentials.scopes

        self.oauth_error_reason = "permission"
        if not set(settings.GOOGLE_DRIVE_SCOPES).issubset(
            set(granted_scopes or [])
        ):
            raise PermissionDenied(
                "The required Google Drive permission was not granted."
            )

        if not credentials.refresh_token:
            raise ValidationError({
                "detail": (
                    "Google did not provide a refresh token. "
                    "Start a new connection and approve access again."
                )
            })

        # Define this before using it in update_or_create().
        credentials_data = json.loads(credentials.to_json())

        # Check that disconnecting did not cancel this attempt.
        with transaction.atomic():
            active_attempt = (
                GoogleOAuthState.objects
                .select_for_update()
                .filter(
                    state_hash=hash_oauth_value(state),
                    user_id=user_id,
                    used_at__isnull=False,
                )
                .first()
            )

            if active_attempt is None:
                raise ValidationError({
                    "detail": (
                        "This Google connection attempt was cancelled. "
                        "Start a new connection."
                    )
                })

            GoogleDriveConnection.objects.update_or_create(
                user_id=user_id,
                defaults={
                    "credentials_encrypted": encrypt_json(
                        credentials_data
                    ),
                },
            )

        return HttpResponseRedirect(f'{self.oauth_return_url}/?google=connected')

    def handle_exception(self, exc):
        if not isinstance(exc, (ValidationError, PermissionDenied, NotFound, Http404)):
            logger.exception("Google OAuth callback failed")
        reason = getattr(self, "oauth_error_reason", "failed")
        return HttpResponseRedirect(
            f'{getattr(self, "oauth_return_url", settings.FRONTEND_URL)}/?google=error&reason={reason}'
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request, response, *args, **kwargs
        )

        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"

        return response
    
class GoogleDriveFolderListView(APIView):
    permission_classes=[IsAuthenticated]
    
    def get(self,request):
        serializer=DriveFolderListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        folder=serializer.validated_data['folder_link']
        page_token=serializer.validated_data.get('page_token', '')
        album_id=serializer.validated_data.get('album_id')
        album = get_object_or_404(Album, pk=album_id, owner=request.user, is_deleted=False) if album_id else None
        service=None
        
        try:
            service=get_drive_service(request.user)
            folder_request=service.files().get(
                fileId=folder['folder_id'],
                fields="id,name,mimeType,driveId",
                supportsAllDrives=True,
            )
            metadata=apply_resource_key(folder_request,folder).execute()
            if metadata['mimeType']!=('application/vnd.google-apps.folder'):
                raise ValidationError({"detail": "The provided folder link is not a folder."})
            
            query=(
                f"'{folder['folder_id']}' in parents "
                "and trashed = false "
                "and (mimeType = 'image/jpeg' "
                "or mimeType = 'image/jpg' "
                "or mimeType = 'image/pjpeg' "
                "or mimeType = 'image/png' "
                "or mimeType = 'image/webp')"
            )
            
            list_options = {
                "q": query,
                "pageSize": 50,
                "pageToken": page_token or None,
                "orderBy": "name_natural",
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
                "fields": (
                    "nextPageToken,"
                    "files(id,name,mimeType,size,thumbnailLink,resourceKey,"
                    "capabilities(canDownload))"
                ),
                "corpora": "user",
            }
            if metadata.get("driveId"):
                list_options["corpora"] = "drive"
                list_options["driveId"] = metadata["driveId"]

            list_request = service.files().list(**list_options)

            result = apply_resource_key(
                list_request, folder
            ).execute()

            files = result.get("files", [])
            if album is not None:
                imported_ids = set(
                    AlbumPhoto.objects.filter(
                        album=album,
                        is_deleted=False,
                        source_drive_file_id__in=[file["id"] for file in files],
                    ).values_list("source_drive_file_id", flat=True)
                )
                for file in files:
                    file["already_imported"] = file["id"] in imported_ids

            response = Response({
                "folder": {
                    "id": metadata["id"],
                    "name": metadata["name"],
                },
                "files": files,
                "next_page_token": result.get("nextPageToken"),
            })
            response["Cache-Control"] = "no-store"
            return response

        except RefreshError:
            raise ValidationError({
                "detail": "Reconnect your Google Drive account."
            })

        except HttpError as exc:
            google_status = int(exc.resp.status)

            if google_status == 400:
                raise ValidationError({
                    "detail": (
                        "Google rejected the request. Check the folder "
                        "link or retry without a page token."
                    )
                })

            if google_status == 401:
                raise ValidationError({
                    "detail": "Reconnect your Google Drive account."
                })

            if google_status == 403:
                raise PermissionDenied(
                    "Google denied the request. Check folder access, "
                    "Drive API configuration, and API quota."
                )

            if google_status == 404:
                raise NotFound(
                    "Folder not found or unavailable to "
                    "your connected Google account."
                )

            return Response(
                {"detail": "Google Drive is temporarily unavailable."},
                status=502,
            )

        except (TransportError, httplib2.HttpLib2Error, OSError):
            return Response(
                {"detail": "Could not connect to Google Drive. Try again."},
                status=502,
            )

        finally:
            if service is not None:
                service.close()
            
            

            

