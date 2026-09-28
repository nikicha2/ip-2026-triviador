from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from auth_app.models import User, Profile


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='player_one',
            email='player@example.com',
            password='example-password',
        )
        self.profile = Profile.objects.create(user=self.user, nickname='MountainKnight', avatar_key='knight-2')

    def test_register_success(self):
        response = self.client.post(
            reverse('auth_app:register'),
            {
                'username': 'player_two',
                'email': 'player2@example.com',
                'nickname': 'SkyKnight',
                'password': 'example-password',
                'password_confirm': 'example-password',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(username='player_two').count(), 1)
        self.assertEqual(Profile.objects.filter(nickname='SkyKnight').count(), 1)
        self.assertNotIn('password', response.data)

    def test_register_invalid_password_confirm(self):
        response = self.client.post(
            reverse('auth_app:register'),
            {
                'username': 'player_two',
                'email': 'player2@example.com',
                'nickname': 'SkyKnight',
                'password': 'example-password',
                'password_confirm': 'different-password',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data['errors'])

    def test_login_success(self):
        response = self.client.post(
            reverse('auth_app:login'),
            {
                'username': 'player_one',
                'password': 'example-password',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('sessionid', response.cookies)
        self.assertTrue(self.client.login(username='player_one', password='example-password'))

    def test_login_invalid_password(self):
        response = self.client.post(
            reverse('auth_app:login'),
            {
                'username': 'player_one',
                'password': 'wrong-password',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_me_requires_authentication(self):
        response = self.client.get(reverse('auth_app:me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user_for_authenticated_user(self):
        self.client.login(username='player_one', password='example-password')
        response = self.client.get(reverse('auth_app:me'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'player_one')

    def test_me_update_profile(self):
        self.client.login(username='player_one', password='example-password')
        response = self.client.patch(
            reverse('auth_app:me'),
            {'nickname': 'NewKnight', 'avatar_key': 'knight-3'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.nickname, 'NewKnight')
        self.assertEqual(self.profile.avatar_key, 'knight-3')

    def test_logout_clears_session(self):
        self.client.login(username='player_one', password='example-password')
        response = self.client.post(reverse('auth_app:logout'))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(reverse('auth_app:me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_csrf_protection_for_unsafe_requests(self):
        self.client.login(username='player_one', password='example-password')
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_client.login(username='player_one', password='example-password')
        response = csrf_client.patch(reverse('auth_app:me'), {'nickname': 'NoCsrf'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authentication_flow_stays_in_session(self):
        login_response = self.client.post(
            reverse('auth_app:login'),
            {'username': 'player_one', 'password': 'example-password'},
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        me_response = self.client.get(reverse('auth_app:me'))
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data['username'], 'player_one')
