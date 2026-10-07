import json

import google_auth_httplib2
import httplib2
from django.utils import timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from rest_framework.exceptions import NotFound

from .crypto import decrypt_json, encrypt_json
from .models import GoogleDriveConnection


def get_drive_service(user):
    try:
        connection = GoogleDriveConnection.objects.get(user=user)
    except GoogleDriveConnection.DoesNotExist:
        raise NotFound("Connect your Google Drive account first.")

    saved_ciphertext = connection.credentials_encrypted
    credentials_data = decrypt_json(saved_ciphertext)

    credentials = Credentials.from_authorized_user_info(
        credentials_data
    )

    http = httplib2.Http(timeout=20)

    if not credentials.valid:
        credentials.refresh(google_auth_httplib2.Request(http))

        # Avoid overwriting credentials from a newer Google connection.
        GoogleDriveConnection.objects.filter(
            pk=connection.pk,
            credentials_encrypted=saved_ciphertext,
        ).update(
            credentials_encrypted=encrypt_json(
                json.loads(credentials.to_json())
            ),
            updated_at=timezone.now(),
        )

    authorized_http = google_auth_httplib2.AuthorizedHttp(
        credentials,
        http=http,
    )

    return build(
        "drive",
        "v3",
        http=authorized_http,
        cache_discovery=False,
    )


def apply_resource_key(api_request, folder):
    if folder["resource_key"]:
        api_request.headers["X-Goog-Drive-Resource-Keys"] = (
            f'{folder["folder_id"]}/{folder["resource_key"]}'
        )

    return api_request