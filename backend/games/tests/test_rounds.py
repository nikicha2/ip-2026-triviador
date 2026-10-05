from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from auth_app.models import User
from games.models import Game, Player, Round


class RoundModelTests(TestCase):
    def setUp(self):
        self.game = Game.objects.create()
        self.users = [
            User.objects.create_user(username='alice', email='alice@example.com', password='pass1234'),
            User.objects.create_user(username='bob', email='bob@example.com', password='pass1234'),
            User.objects.create_user(username='carol', email='carol@example.com', password='pass1234'),
        ]
        self.players = []
        for user, color in zip(self.users, [Player.Color.RED, Player.Color.GREEN, Player.Color.BLUE]):
            self.players.append(Player.objects.create(game=self.game, user=user, color=color))
        self.game.start()

    def test_create_round_with_valid_defaults(self):
        round_obj = Round.objects.create(
            game=self.game,
            number=1,
            type=Round.Type.CITY_CAPTURE,
            status=Round.Status.PENDING,
        )

        self.assertEqual(round_obj.type, Round.Type.CITY_CAPTURE)
        self.assertEqual(round_obj.status, Round.Status.PENDING)
        self.assertIsNone(round_obj.winner)
        self.assertIsNone(round_obj.completed_at)

    def test_round_type_and_status_choices(self):
        self.assertEqual(Round.Type.choices, [
            ('city_capture', 'City capture'),
            ('battle', 'Battle'),
            ('capital_attack', 'Capital attack'),
            ('bonus', 'Bonus'),
        ])
        self.assertEqual(Round.Status.choices, [
            ('pending', 'Pending'),
            ('active', 'Active'),
            ('completed', 'Completed'),
        ])

    def test_round_numbers_are_unique_within_game(self):
        Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Round.objects.create(game=self.game, number=1, type=Round.Type.BATTLE)

    def test_same_round_number_can_be_used_in_different_games(self):
        other_game = Game.objects.create()
        other_users = [
            User.objects.create_user(username='dave', email='dave@example.com', password='pass1234'),
            User.objects.create_user(username='erin', email='erin@example.com', password='pass1234'),
            User.objects.create_user(username='frank', email='frank@example.com', password='pass1234'),
        ]
        for user, color in zip(other_users, [Player.Color.RED, Player.Color.GREEN, Player.Color.BLUE]):
            Player.objects.create(game=other_game, user=user, color=color)
        other_game.start()

        Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        Round.objects.create(game=other_game, number=1, type=Round.Type.BATTLE)

    def test_pending_round_has_no_winner_or_completion_time(self):
        round_obj = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)

        self.assertEqual(round_obj.status, Round.Status.PENDING)
        self.assertIsNone(round_obj.winner)
        self.assertIsNone(round_obj.completed_at)

    def test_only_active_games_can_have_new_rounds(self):
        waiting_game = Game.objects.create()
        with self.assertRaises(ValidationError):
            Round.objects.create(game=waiting_game, number=1, type=Round.Type.BATTLE)

    def test_round_can_transition_from_pending_to_active(self):
        round_obj = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)

        round_obj.activate()

        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, Round.Status.ACTIVE)

    def test_only_one_active_round_may_exist_per_game(self):
        round_one = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        round_one.activate()

        with self.assertRaises(ValidationError):
            Round.objects.create(game=self.game, number=2, type=Round.Type.BATTLE)

    def test_round_can_be_completed_with_winner_from_same_game(self):
        round_obj = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        round_obj.activate()

        round_obj.complete(self.players[0])

        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, Round.Status.COMPLETED)
        self.assertEqual(round_obj.winner, self.players[0])
        self.assertIsNotNone(round_obj.completed_at)

    def test_round_cannot_be_completed_with_player_from_other_game(self):
        other_game = Game.objects.create()
        other_user = User.objects.create_user(username='dave', email='dave@example.com', password='pass1234')
        other_player = Player.objects.create(game=other_game, user=other_user, color=Player.Color.RED)
        round_obj = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        round_obj.activate()

        with self.assertRaises(ValidationError):
            round_obj.complete(other_player)

    def test_invalid_lifecycle_transitions_are_rejected(self):
        round_obj = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)

        with self.assertRaises(ValidationError):
            round_obj.complete(self.players[0])

        round_obj.activate()
        with self.assertRaises(ValidationError):
            round_obj.activate()

    def test_get_current_round_returns_highest_number(self):
        self.game.status = Game.Status.ACTIVE
        self.game.save(update_fields=['status'])

        round_one = Round.objects.create(game=self.game, number=1, type=Round.Type.CITY_CAPTURE)
        round_two = Round.objects.create(game=self.game, number=2, type=Round.Type.BATTLE)

        self.assertEqual(self.game.get_current_round(), round_two)
        self.assertEqual(round_one.game, self.game)
