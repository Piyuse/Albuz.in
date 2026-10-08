from django.conf import settings
from django.test import SimpleTestCase


class PublicApiOriginTests(SimpleTestCase):
    def test_configured_frontend_origin_can_call_api(self):
        response = self.client.options(
            '/api/auth/login/',
            HTTP_ORIGIN=settings.FRONTEND_URL,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        self.assertEqual(response['Access-Control-Allow-Origin'], settings.FRONTEND_URL)

    def test_other_origin_cannot_call_api(self):
        response = self.client.options(
            '/api/auth/login/',
            HTTP_ORIGIN='https://unknown.example',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        self.assertNotIn('Access-Control-Allow-Origin', response)
