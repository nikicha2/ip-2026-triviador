from django.test import TestCase

from auth_app.models import User
from games.models import Game, Player, WaitingRoom
from games.services.waiting_room import form_game, join_waiting_room


class DeterministicRng:
    def __init__(self, sample_order=None):
        self.sample_order = sample_order

    def sample(self, population, k):
        if self.sample_order is not None:
            selected = [user for user in self.sample_order if user in population]
            return selected[:k]
        return list(population)[:k]

    def shuffle(self, sequence):
        return None


class WaitingRoomFormationTests(TestCase):
    def _make_users(self, count):
        return [
            User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='pass1234',
            )
            for i in range(count)
        ]

    def _enqueue(self, users):
        for user in users:
            join_waiting_room(user)

    def test_form_game_with_five_waiters_creates_game_and_leaves_two(self):
        users = self._make_users(5)
        game = Game.objects.create(status=Game.Status.WAITING)
        room = WaitingRoom.objects.create(game=game, is_active=True)
        room.waiting.add(*users)

        games_before = Game.objects.count()
        formed = form_game(room=room, rng=DeterministicRng(sample_order=users[:3]))

        self.assertIsNotNone(formed)
        formed.refresh_from_db()
        self.assertEqual(formed.status, Game.Status.WAITING)
        self.assertEqual(formed.players.count(), 3)

        player_users = set(formed.players.values_list('user_id', flat=True))
        self.assertEqual(player_users, {users[0].pk, users[1].pk, users[2].pk})

        colors = list(formed.players.values_list('color', flat=True))
        self.assertEqual(sorted(colors), sorted([
            Player.Color.RED,
            Player.Color.GREEN,
            Player.Color.BLUE,
        ]))
        self.assertTrue(all(score == 0 for score in formed.players.values_list('score', flat=True)))

        room.refresh_from_db()
        self.assertFalse(room.is_active)
        self.assertEqual(room.waiting.count(), 0)

        active_room = WaitingRoom.objects.get(is_active=True)
        remaining = set(active_room.waiting.values_list('id', flat=True))
        self.assertEqual(remaining, {users[3].pk, users[4].pk})

        self.assertEqual(Game.objects.count(), games_before + 1)
        self.assertEqual(Game.objects.filter(status=Game.Status.WAITING).count(), 2)
        self.assertFalse(formed.territories.exists())
        self.assertFalse(formed.rounds.exists())

    def test_form_game_with_two_waiters_makes_no_changes(self):
        users = self._make_users(2)
        game = Game.objects.create(status=Game.Status.WAITING)
        room = WaitingRoom.objects.create(game=game, is_active=True)
        room.waiting.add(*users)

        games_before = list(Game.objects.values_list('id', 'status'))
        rooms_before = list(WaitingRoom.objects.values_list('id', 'is_active'))
        waiters_before = set(room.waiting.values_list('id', flat=True))
        players_before = Player.objects.count()

        formed = form_game(room=room)

        self.assertIsNone(formed)
        room.refresh_from_db()
        self.assertTrue(room.is_active)
        self.assertEqual(set(room.waiting.values_list('id', flat=True)), waiters_before)
        self.assertEqual(Player.objects.count(), players_before)
        self.assertEqual(list(Game.objects.values_list('id', 'status')), games_before)
        self.assertEqual(list(WaitingRoom.objects.values_list('id', 'is_active')), rooms_before)
