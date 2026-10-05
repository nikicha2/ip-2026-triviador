from django.db import IntegrityError, transaction
from django.test import TestCase

from auth_app.models import User
from games.models import Game, Player


class PlayerModelTests(TestCase):
    def setUp(self):
        self.game = Game.objects.create()
        self.user = User.objects.create_user(username='alice', email='alice@example.com', password='pass1234')

    def test_creates_player_with_valid_defaults(self):
        player = Player.objects.create(game=self.game, user=self.user, color=Player.Color.RED)

        self.assertEqual(player.score, 0)
        self.assertEqual(player.color, Player.Color.RED)
        self.assertEqual(player.game, self.game)

    def test_all_colors_are_available(self):
        self.assertEqual(Player.Color.choices, [('red', 'Red'), ('green', 'Green'), ('blue', 'Blue')])

    def test_duplicate_user_in_same_game_is_rejected(self):
        Player.objects.create(game=self.game, user=self.user, color=Player.Color.RED)

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Player.objects.create(game=self.game, user=self.user, color=Player.Color.GREEN)

    def test_duplicate_color_in_same_game_is_rejected(self):
        Player.objects.create(game=self.game, user=self.user, color=Player.Color.RED)
        other_user = User.objects.create_user(username='bob', email='bob@example.com', password='pass1234')

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Player.objects.create(game=self.game, user=other_user, color=Player.Color.RED)

    def test_negative_score_is_rejected_by_database_constraint(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Player.objects.create(game=self.game, user=self.user, color=Player.Color.RED, score=-1)

    def test_same_user_can_join_different_games(self):
        other_game = Game.objects.create()
        Player.objects.create(game=self.game, user=self.user, color=Player.Color.RED)
        Player.objects.create(game=other_game, user=self.user, color=Player.Color.BLUE)

        self.assertEqual(self.game.players.count(), 1)
        self.assertEqual(other_game.players.count(), 1)

    def test_same_color_can_be_reused_in_different_games(self):
        other_game = Game.objects.create()
        Player.objects.create(game=self.game, user=self.user, color=Player.Color.RED)
        other_user = User.objects.create_user(username='bob', email='bob@example.com', password='pass1234')
        Player.objects.create(game=other_game, user=other_user, color=Player.Color.RED)

        self.assertEqual(self.game.players.count(), 1)
        self.assertEqual(other_game.players.count(), 1)

    def test_fourth_player_cannot_join_game_with_three_players(self):
        users = [
            User.objects.create_user(username='bob', email='bob@example.com', password='pass1234'),
            User.objects.create_user(username='carol', email='carol@example.com', password='pass1234'),
            User.objects.create_user(username='dave', email='dave@example.com', password='pass1234'),
        ]
        colors = [Player.Color.RED, Player.Color.GREEN, Player.Color.BLUE]
        for user, color in zip(users, colors):
            Player.objects.create(game=self.game, user=user, color=color)

        four_user = User.objects.create_user(username='erin', email='erin@example.com', password='pass1234')
        with self.assertRaises(Exception):
            Player.objects.create(game=self.game, user=four_user, color='red')
