from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


class Game(models.Model):
    class Status(models.TextChoices):
        WAITING = 'waiting', 'Waiting'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'

    WAITING = Status.WAITING
    ACTIVE = Status.ACTIVE
    COMPLETED = Status.COMPLETED

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Game {self.pk} - {self.status}'

    def get_current_round(self):
        return self.rounds.order_by('-number').first()

    def is_active(self):
        return self.status == self.Status.ACTIVE

    def is_completed(self):
        return self.status == self.Status.COMPLETED

    @transaction.atomic
    def start(self):
        game = Game.objects.select_for_update().get(pk=self.pk)

        if game.status != self.Status.WAITING:
            raise ValidationError('A game can only start while waiting.')
        if game.players.count() != 3:
            raise ValidationError('A game must have exactly three players to start.')

        game.status = self.Status.ACTIVE
        game.save(update_fields=['status'])
        return game


class Player(models.Model):
    class Color(models.TextChoices):
        RED = 'red', 'Red'
        GREEN = 'green', 'Green'
        BLUE = 'blue', 'Blue'

    RED = Color.RED
    GREEN = Color.GREEN
    BLUE = Color.BLUE

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='players',
    )
    score = models.IntegerField(default=0)
    color = models.CharField(
        max_length=20,
        choices=Color.choices,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'game'],
                name='unique_user_per_game',
            ),
            models.UniqueConstraint(
                fields=['game', 'color'],
                name='unique_color_per_game',
            ),
            models.CheckConstraint(
                condition=models.Q(score__gte=0),
                name='player_score_gte_0',
            ),
        ]

    def __str__(self):
        return f'{self.user} in game {self.game_id}'

    def clean(self):
        super().clean()

        if self.game_id and self.game.status == Game.Status.COMPLETED:
            raise ValidationError('Completed games cannot accept new players.')
        if self.game_id and self.game.status != Game.Status.WAITING:
            raise ValidationError('Players can only join waiting games.')
        if self.score < 0:
            raise ValidationError('Player score cannot be negative.')
        if self.game_id and self.game.players.exclude(pk=self.pk).filter(user=self.user).exists():
            raise ValidationError('A user can only join a game once.')
        if self.game_id and self.game.players.exclude(pk=self.pk).filter(color=self.color).exists():
            raise ValidationError('A color can only be used once per game.')
        if self.game_id and self.game.players.count() >= 3 and self.pk is None:
            raise ValidationError('A game can have at most three players.')

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding and self.game_id is not None:
            game = Game.objects.select_for_update().get(pk=self.game_id)
            if game.status == Game.Status.COMPLETED:
                raise ValidationError('Completed games cannot accept new players.')
            if game.status != Game.Status.WAITING:
                raise ValidationError('Players can only join waiting games.')
            if game.players.count() >= 3:
                raise ValidationError('A game can have at most three players.')
        return super().save(*args, **kwargs)


class Round(models.Model):
    class Type(models.TextChoices):
        CITY_CAPTURE = 'city_capture', 'City capture'
        BATTLE = 'battle', 'Battle'
        CAPITAL_ATTACK = 'capital_attack', 'Capital attack'
        BONUS = 'bonus', 'Bonus'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'

    PENDING = Status.PENDING
    ACTIVE = Status.ACTIVE
    COMPLETED = Status.COMPLETED

    CITY_CAPTURE = Type.CITY_CAPTURE
    BATTLE = Type.BATTLE
    CAPITAL_ATTACK = Type.CAPITAL_ATTACK
    BONUS = Type.BONUS

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='rounds',
    )
    number = models.PositiveIntegerField()
    type = models.CharField(
        max_length=30,
        choices=Type.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    winner = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_rounds',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['number']
        constraints = [
            models.UniqueConstraint(
                fields=['game', 'number'],
                name='unique_round_number_per_game',
            ),
            models.UniqueConstraint(
                fields=['game'],
                condition=models.Q(status='active'),
                name='unique_active_round_per_game',
            ),
        ]

    def __str__(self):
        return f'Round {self.number} ({self.type})'

    def clean(self):
        super().clean()

        if self.game_id and self.game.status == Game.Status.COMPLETED:
            raise ValidationError('Completed games cannot receive new rounds.')
        if self.game_id and self.status == self.Status.ACTIVE and self.game.status != Game.Status.ACTIVE:
            raise ValidationError('Only active games can have active rounds.')
        if self.winner_id is not None and self.winner.game_id != self.game_id:
            raise ValidationError('A round winner must belong to the same game.')

        if self.status == self.Status.PENDING:
            if self.winner_id is not None or self.completed_at is not None:
                raise ValidationError('Pending rounds cannot have a winner or completion timestamp.')
        if self.status == self.Status.COMPLETED:
            if self.winner_id is None or self.completed_at is None:
                raise ValidationError('Completed rounds must have a winner and a completion timestamp.')

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding and self.game_id is not None:
            game = Game.objects.select_for_update().get(pk=self.game_id)
            if game.status != Game.Status.ACTIVE:
                raise ValidationError('New rounds can only be created for active games.')
            if game.rounds.filter(status=self.Status.ACTIVE).exclude(pk=self.pk).exists():
                raise ValidationError('A game can have at most one active round.')
        return super().save(*args, **kwargs)

    @transaction.atomic
    def activate(self):
        round_obj = Round.objects.select_for_update().get(pk=self.pk)

        if round_obj.game.status != Game.Status.ACTIVE:
            raise ValidationError('Only active games can host active rounds.')
        if round_obj.status != self.Status.PENDING:
            raise ValidationError('Only pending rounds can be activated.')
        if round_obj.game.rounds.filter(status=self.Status.ACTIVE).exclude(pk=round_obj.pk).exists():
            raise ValidationError('A game already has an active round.')

        round_obj.status = self.Status.ACTIVE
        round_obj.winner = None
        round_obj.completed_at = None
        round_obj.save(update_fields=['status', 'winner', 'completed_at'])
        return round_obj

    @transaction.atomic
    def complete(self, winner):
        round_obj = Round.objects.select_for_update().get(pk=self.pk)

        if round_obj.status != self.Status.ACTIVE:
            raise ValidationError('Only active rounds can be completed.')
        if not isinstance(winner, Player):
            raise ValidationError('The winner must be a player instance.')
        if winner.game_id != round_obj.game_id:
            raise ValidationError('The winner must belong to the same game.')

        round_obj.status = self.Status.COMPLETED
        round_obj.winner = winner
        round_obj.completed_at = timezone.now()
        round_obj.full_clean()
        round_obj.save(update_fields=['status', 'winner', 'completed_at'])
        return round_obj
