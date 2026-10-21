from __future__ import annotations

import random
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from games.models import Game, Player, WaitingRoom

BUSY_GAME_STATUSES = (Game.Status.WAITING, Game.Status.ACTIVE)
PLAYER_COLORS = (Player.Color.RED, Player.Color.GREEN, Player.Color.BLUE)


def user_is_in_busy_game(user) -> bool:
    return Player.objects.filter(
        user=user,
        game__status__in=BUSY_GAME_STATUSES,
    ).exists()


def user_is_waiting(user) -> bool:
    return WaitingRoom.objects.filter(is_active=True, waiting=user).exists()


def can_join_waiting_room(user) -> bool:
    if user_is_waiting(user):
        return False
    if user_is_in_busy_game(user):
        return False
    return True


def _get_active_room_for_update() -> Optional[WaitingRoom]:
    return (
        WaitingRoom.objects.select_for_update()
        .filter(is_active=True)
        .first()
    )


def _create_active_room() -> WaitingRoom:
    game = Game.objects.create(status=Game.Status.WAITING)
    return WaitingRoom.objects.create(game=game, is_active=True)


@transaction.atomic
def join_waiting_room(user) -> WaitingRoom:
    if user_is_waiting(user):
        raise ValidationError('User already has an active waiting-room request.')

    if user_is_in_busy_game(user):
        raise ValidationError(
            'User already participates in a waiting or active game.'
        )

    room = _get_active_room_for_update()
    if room is None:
        room = _create_active_room()
        room = WaitingRoom.objects.select_for_update().get(pk=room.pk)

    room.waiting.add(user)

    if _eligible_waiter_count(room) >= 3:
        form_game(room=room)

    return room


@transaction.atomic
def leave_waiting_room(user) -> None:
    room = (
        WaitingRoom.objects.select_for_update()
        .filter(is_active=True, waiting=user)
        .first()
    )
    if room is None:
        return
    room.waiting.remove(user)


def _eligible_waiters(room: WaitingRoom):
    busy_user_ids = set(
        Player.objects.filter(game__status__in=BUSY_GAME_STATUSES)
        .values_list('user_id', flat=True)
    )
    return [user for user in room.waiting.all() if user.pk not in busy_user_ids]


def _eligible_waiter_count(room: WaitingRoom) -> int:
    return len(_eligible_waiters(room))


@transaction.atomic
def form_game(
    room: Optional[WaitingRoom] = None,
    rng=random,
) -> Optional[Game]:
    if room is None:
        room = _get_active_room_for_update()
    else:
        room = WaitingRoom.objects.select_for_update().get(pk=room.pk)

    if room is None or not room.is_active:
        return None

    eligible = _eligible_waiters(room)
    if len(eligible) < 3:
        return None

    selected = rng.sample(eligible, 3)
    colors = list(PLAYER_COLORS)
    rng.shuffle(colors)

    game = Game.objects.select_for_update().get(pk=room.game_id)
    if game.status != Game.Status.WAITING:
        raise ValidationError('Waiting room game must be in waiting status.')
    if game.players.exists():
        raise ValidationError('Waiting room game already has players.')

    for user, color in zip(selected, colors):
        Player.objects.create(game=game, user=user, color=color, score=0)

    room.waiting.remove(*selected)

    remaining = list(room.waiting.all())
    room.waiting.clear()
    room.is_active = False
    room.save(update_fields=['is_active'])

    if remaining:
        new_room = _create_active_room()
        new_room.waiting.add(*remaining)

    return game
