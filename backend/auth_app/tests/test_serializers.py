from django.test import TestCase

from auth_app.models import User, Profile
from auth_app.serializers import RegisterSerializer, MeSerializer


class RegisterSerializerTests(TestCase):
    def test_register_serializer_creates_user_and_profile(self):
        data = {
            'username': 'player_one',
            'email': 'player@example.com',
            'nickname': 'MountainKnight',
            'password': 'example-password',
            'password_confirm': 'example-password',
        }

        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertEqual(user.username, 'player_one')
        self.assertEqual(user.email, 'player@example.com')
        self.assertTrue(user.check_password('example-password'))
        self.assertEqual(user.profile.nickname, 'MountainKnight')
        self.assertEqual(user.profile.avatar_key, 'knight-1')

    def test_register_serializer_validates_passwords_match(self):
        data = {
            'username': 'player_one',
            'email': 'player@example.com',
            'nickname': 'MountainKnight',
            'password': 'example-password',
            'password_confirm': 'different-password',
        }

        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password_confirm', serializer.errors)

    def test_me_serializer_restricts_editable_fields(self):
        user = User.objects.create_user(
            username='player_one',
            email='player@example.com',
            password='example-password',
        )
        Profile.objects.create(user=user, nickname='MountainKnight', avatar_key='knight-2')

        serializer = MeSerializer(user, data={'nickname': 'NewKnight', 'avatar_key': 'knight-3', 'email': 'hacker@example.com'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['nickname'], 'NewKnight')
        self.assertEqual(serializer.validated_data['avatar_key'], 'knight-3')
        self.assertNotIn('email', serializer.validated_data)
