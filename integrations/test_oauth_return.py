import json
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from integrations.models import GoogleDriveConnection


@override_settings(
    FRONTEND_URL="http://127.0.0.1:5173",
    GOOGLE_REDIRECT_URI="http://127.0.0.1:8000/api/integrations/google/callback/",
    GOOGLE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
)
class OAuthReturnTests(APITestCase):
    def test_missing_state_returns_to_frontend(self):
        response = self.client.get("/api/integrations/google/callback/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "http://127.0.0.1:5173/?google=error&reason=expired",
        )

    def test_expired_state_returns_to_frontend(self):
        response = self.client.get("/api/integrations/google/callback/?state=expired")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "http://127.0.0.1:5173/?google=error&reason=expired",
        )

    @patch("integrations.views.build_google_flow")
    def test_localhost_origin_connects_without_callback_cookie(self, build_flow):
        user = get_user_model().objects.create_user(
            username="oauth_host_test",
            email="oauth-host@example.com",
            password="test-password-123",
        )
        self.client.force_authenticate(user=user)
        flow = Mock()
        flow.authorization_url.return_value = ("https://accounts.google.com/test", "test-state")
        flow.credentials.granted_scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        flow.credentials.refresh_token = "refresh-token"
        flow.credentials.to_json.return_value = json.dumps({"refresh_token": "refresh-token"})
        build_flow.return_value = flow

        response = self.client.post(
            "/api/integrations/google/connect/",
            {"return_origin": "http://localhost:5173"},
            format="json",
            HTTP_HOST="localhost:5173",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["authorization_url"], "https://accounts.google.com/test")

        self.client.force_authenticate(user=None)
        response = self.client.get(
            "/api/integrations/google/callback/?state=test-state&code=test-code",
            HTTP_HOST="127.0.0.1:8000",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://localhost:5173/?google=connected")
        self.assertTrue(GoogleDriveConnection.objects.filter(user=user).exists())

        replay = self.client.get(
            "/api/integrations/google/callback/?state=test-state&code=test-code",
            HTTP_HOST="127.0.0.1:8000",
        )
        self.assertEqual(replay["Location"], "http://127.0.0.1:5173/?google=error&reason=expired")
        self.assertEqual(flow.fetch_token.call_count, 1)

    @patch("integrations.views.build_google_flow")
    def test_rejects_unapproved_return_origin(self, build_flow):
        user = get_user_model().objects.create_user(
            username="oauth_origin_test",
            email="oauth-origin@example.com",
            password="test-password-123",
        )
        self.client.force_authenticate(user=user)
        response = self.client.post(
            "/api/integrations/google/connect/",
            {"return_origin": "https://example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        build_flow.assert_not_called()

    @override_settings(GOOGLE_TOKEN_ENCRYPTION_KEY="invalid-key")
    @patch("integrations.views.logger")
    @patch("integrations.views.build_google_flow")
    def test_connect_reports_invalid_encryption_key_as_json(self, build_flow, logger):
        user = get_user_model().objects.create_user(
            username="oauth_invalid_key_test",
            password="test-password-123",
        )
        self.client.force_authenticate(user=user)
        build_flow.return_value.authorization_url.return_value = (
            "https://accounts.google.com/test", "test-state"
        )

        response = self.client.post(
            "/api/integrations/google/connect/",
            {"return_origin": "http://127.0.0.1:5173"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.data["detail"],
            "Google Drive encryption setup failed on the server.",
        )
        logger.exception.assert_called_once()

    @patch("integrations.views.logger")
    @patch("integrations.views.GoogleOAuthState.objects.create")
    @patch("integrations.views.build_google_flow")
    def test_connect_reports_state_save_failure_as_json(self, build_flow, create, logger):
        user = get_user_model().objects.create_user(
            username="oauth_state_save_test",
            password="test-password-123",
        )
        self.client.force_authenticate(user=user)
        build_flow.return_value.authorization_url.return_value = (
            "https://accounts.google.com/test", "test-state"
        )
        create.side_effect = RuntimeError("database unavailable")

        response = self.client.post(
            "/api/integrations/google/connect/",
            {"return_origin": "http://127.0.0.1:5173"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.data["detail"],
            "Google Drive could not save the connection attempt.",
        )
        logger.exception.assert_called_once()
