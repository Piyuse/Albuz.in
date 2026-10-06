from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from google_auth_oauthlib.flow import Flow


def build_google_flow(state=None, code_verifier=None):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise ImproperlyConfigured(
            "Configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."
        )

    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }

    return Flow.from_client_config(
        client_config,
        scopes=settings.GOOGLE_DRIVE_SCOPES,
        state=state,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
        code_verifier=code_verifier,
        autogenerate_code_verifier=False,
    )