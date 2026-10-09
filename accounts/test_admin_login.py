from django.contrib.auth import get_user_model
from django.test import TestCase


class AdminUsersTests(TestCase):
    def test_jwt_login_updates_last_login_and_admin_lists_user(self):
        User = get_user_model()
        member = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='test-password-123',
        )
        self.assertIsNone(member.last_login)

        response = self.client.post(
            '/api/auth/login/',
            data='{"username":"member","password":"test-password-123"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        member.refresh_from_db()
        self.assertIsNotNone(member.last_login)

        admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='test-password-123',
        )
        self.client.force_login(admin)
        response = self.client.get('/admin/accounts/user/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'member@example.com')
        self.assertContains(response, 'Last login')

    def test_login_endpoint_is_throttled(self):
        for attempt in range(11):
            response = self.client.post(
                '/api/auth/login/',
                data='{"username":"unknown","password":"wrong-password"}',
                content_type='application/json',
                REMOTE_ADDR='192.0.2.25',
            )
            self.assertEqual(response.status_code, 429 if attempt == 10 else 401)
