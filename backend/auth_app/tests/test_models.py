from django.test import TestCase

from auth_app.models import User, Profile


class UserProfileModelTests(TestCase):
    def test_user_and_profile_are_created(self):
        user = User.objects.create_user(
            username='player_one',
            email='player@example.com',
            password='example-password',
        )
        profile = Profile.objects.create(user=user, nickname='MountainKnight')

        self.assertEqual(user.email, 'player@example.com')
        self.assertTrue(user.check_password('example-password'))
        self.assertEqual(profile.user, user)
        self.assertEqual(profile.nickname, 'MountainKnight')
        self.assertEqual(profile.avatar_key, 'knight-1')

    def test_unique_nickname_is_enforced(self):
        user = User.objects.create_user(
            username='player_one',
            email='player@example.com',
            password='example-password',
        )
        Profile.objects.create(user=user, nickname='MountainKnight')

        second_user = User.objects.create_user(
            username='player_two',
            email='player2@example.com',
            password='example-password',
        )

        with self.assertRaises(Exception):
            Profile.objects.create(user=second_user, nickname='MountainKnight')
