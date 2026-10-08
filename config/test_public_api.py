from django.test import SimpleTestCase


class PublicApiOriginTests(SimpleTestCase):
    def test_configured_frontend_origin_can_call_api(self):
        response = self.client.options(
            '/api/auth/login/',
            HTTP_ORIGIN='http://127.0.0.1:5173',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://127.0.0.1:5173')

    def test_other_origin_cannot_call_api(self):
        response = self.client.options(
            '/api/auth/login/',
            HTTP_ORIGIN='https://unknown.example',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        self.assertNotIn('Access-Control-Allow-Origin', response)
