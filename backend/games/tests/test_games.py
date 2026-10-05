from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from auth_app.models import User
from games.models import Game, Player, Round


class GameModelTests(TestCase):
    def setUp(self):
        self.users = [
            User.objects.create_user(username='alice', email='alice@example.com', password='pass1234'),
            User.objects.create_user(username='bob', email='bob@example.com', password='pass1234'),
            User.objects.create_user(username='carol', email='carol@example.com', password='pass1234'),
        ]
        self.game = Game.objects.create()

    def _make_player(self, user, color, score=0):
        return Player.objects.create(game=self.game, user=user, color=color, score=score)

    def test_game_creation_defaults(self):
        self.assertEqual(self.game.status, Game.Status.WAITING)
        self.assertIsNotNone(self.game.created_at)
        self.assertEqual(list(self.game.players.all()), [])

    def test_get_current_round_returns_highest_number_or_none(self):
        self.game.status = Game.Status.ACTIVE
        self.game.save(update_fields=['status'])

        self.assertIsNone(self.game.get_current_round())

        round_one = Round.objects.create(
            game=self.game,
            number=1,
            type=Round.Type.BATTLE,
            status=Round.Status.PENDING,
        )
        round_two = Round.objects.create(
            game=self.game,
            number=2,
            type=Round.Type.CITY_CAPTURE,
            status=Round.Status.PENDING,
        )

        self.assertEqual(self.game.get_current_round(), round_two)
        self.assertEqual(self.game.get_current_round().number, 2)
        self.assertNotEqual(self.game.get_current_round(), round_one)

    def test_is_active_and_is_completed_flags(self):
        self.assertFalse(self.game.is_active())
        self.assertFalse(self.game.is_completed())

        self.game.status = Game.Status.ACTIVE
        self.game.save(update_fields=['status'])
        self.assertTrue(self.game.is_active())
        self.assertFalse(self.game.is_completed())

        self.game.status = Game.Status.COMPLETED
        self.game.save(update_fields=['status'])
        self.assertFalse(self.game.is_active())
        self.assertTrue(self.game.is_completed())

    def test_game_cannot_start_without_three_players(self):
        self._make_player(self.users[0], Player.Color.RED)
        self._make_player(self.users[1], Player.Color.GREEN)

        with self.assertRaises(ValidationError):
            self.game.start()

    def test_game_with_three_players_can_start(self):
        self._make_player(self.users[0], Player.Color.RED)
        self._make_player(self.users[1], Player.Color.GREEN)
        self._make_player(self.users[2], Player.Color.BLUE)

        self.game.start()

        self.game.refresh_from_db()
        self.assertEqual(self.game.status, Game.Status.ACTIVE)

    def test_already_active_or_completed_game_cannot_be_started_again(self):
        self.game.status = Game.Status.ACTIVE
        self.game.save(update_fields=['status'])

        with self.assertRaises(ValidationError):
            self.game.start()

        self.game.status = Game.Status.COMPLETED
        self.game.save(update_fields=['status'])

        with self.assertRaises(ValidationError):
            self.game.start()

    def test_completed_game_rejects_new_players_and_rounds(self):
        for user, color in zip(self.users, [Player.Color.RED, Player.Color.GREEN, Player.Color.BLUE]):
            self._make_player(user, color)
        self.game.start()
        self.game.status = Game.Status.COMPLETED
        self.game.save(update_fields=['status'])

        with self.assertRaises(ValidationError):
            Player.objects.create(
                game=self.game,
                user=User.objects.create_user(username='dave', email='dave@example.com', password='pass1234'),
                color=Player.Color.RED,
            )

        with self.assertRaises(ValidationError):
            Round.objects.create(
                game=self.game,
                number=1,
                type=Round.Type.BATTLE,
                status=Round.Status.PENDING,
            )

    def test_player_limit_is_enforced(self):
        for user, color in zip(self.users, [Player.Color.RED, Player.Color.GREEN, Player.Color.BLUE]):
            self._make_player(user, color)

        with self.assertRaises(ValidationError):
            Player.objects.create(
                game=self.game,
                user=User.objects.create_user(username='erin', email='erin@example.com', password='pass1234'),
                color=Player.Color.RED,
            )


class GameLifecycleConcurrencyTests(TestCase):
    def test_fourth_player_is_rejected_when_game_is_full(self):
        game = Game.objects.create()
        users = [
            User.objects.create_user(username='frank', email='frank@example.com', password='pass1234'),
            User.objects.create_user(username='grace', email='grace@example.com', password='pass1234'),
            User.objects.create_user(username='heidi', email='heidi@example.com', password='pass1234'),
        ]

        for user, color in zip(users, [Player.Color.RED, Player.Color.GREEN, Player.Color.BLUE]):
            Player.objects.create(game=game, user=user, color=color)

        with self.assertRaises(ValidationError):
            Player.objects.create(
                game=game,
                user=User.objects.create_user(username='ivan', email='ivan@example.com', password='pass1234'),
                color=Player.Color.RED,
            )
