from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Game(models.Model):
    WAITING = 'waiting'
    IN_PROGRESS = 'in_progress'
    FINISHED = 'finished'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (WAITING, "Waiting"),
        (IN_PROGRESS, "In Progress"),
        (FINISHED, "Finished"),
        (CANCELLED, "Cancelled"),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_games'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=WAITING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Game {self.pk} - {self.status}'


class GamePlayer(models.Model):
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='game_players',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='game_players',
    )
    player_order = models.PositiveSmallIntegerField()
    score = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['player_order']
        constraints = [
            models.UniqueConstraint(
                fields=['game', 'user'],
                name='unique_game_player_per_user_per_game',
            ),
            models.UniqueConstraint(
                fields=['game', 'player_order'],
                name='unique_player_order_per_game',
            ),
        ]

    def __str__(self):
        return f'{self.user} in {self.game}'


class Round(models.Model):
    PENDING = 'pending'
    OPEN = 'open'
    CLOSED = 'closed'
    EVALUATED = 'evaluated'

    ROUND_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (OPEN, 'Open'),
        (CLOSED, 'Closed'),
        (EVALUATED, 'Evaluated'),
    ]

    CHOICE = 'choice'
    NUMERIC = 'numeric'

    QUESTION_TYPE_CHOICES = [
        (CHOICE, 'Choice'),
        (NUMERIC, 'Numeric'),
    ]

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='rounds',
    )
    number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=ROUND_STATUS_CHOICES,
        default=PENDING,
    )
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
    )
    choice_question = models.ForeignKey(
        'questions.ChoiceQuestion',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rounds_as_choice_question',
    )
    numeric_question = models.ForeignKey(
        'questions.NumericQuestion',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rounds_as_numeric_question',
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['number']
        constraints = [
            models.UniqueConstraint(
                fields=['game', 'number'],
                name='unique_round_number_per_game',
            ),
            models.CheckConstraint(
                condition=(
                    Q(question_type='choice', choice_question__isnull=False, numeric_question__isnull=True)
                    | Q(question_type='numeric', choice_question__isnull=True, numeric_question__isnull=False)
                ),
                name='round_question_reference_matches_type',
            ),
        ]

    def clean(self):
        super().clean()

        if self.choice_question_id is not None and self.numeric_question_id is not None:
            raise ValidationError('A round cannot reference both a choice and numeric question.')
        if self.choice_question_id is None and self.numeric_question_id is None:
            raise ValidationError('A round must reference exactly one question.')

        if self.question_type == self.CHOICE:
            if self.choice_question_id is None or self.numeric_question_id is not None:
                raise ValidationError('Choice rounds must reference a choice question and no numeric question.')
        elif self.question_type == self.NUMERIC:
            if self.numeric_question_id is None or self.choice_question_id is not None:
                raise ValidationError('Numeric rounds must reference a numeric question and no choice question.')

    def __str__(self):
        return f'Round {self.number} ({self.get_question_type_display()})'


class RoundAnswer(models.Model):
    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    player = models.ForeignKey(
        GamePlayer,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    selected_option = models.ForeignKey(
        'questions.AnswerOption',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='round_answers',
    )
    numeric_value = models.IntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    points_awarded = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['submitted_at']
        constraints = [
            models.UniqueConstraint(
                fields=['round', 'player'],
                name='unique_round_answer_per_player',
            ),
            models.CheckConstraint(
                condition=~Q(selected_option__isnull=False, numeric_value__isnull=False),
                name='roundanswer_not_both_selected_option_and_numeric_value',
            ),
        ]

    def clean(self):
        super().clean()

        if self.round_id and self.player_id and self.player.game_id != self.round.game_id:
            raise ValidationError('A player cannot answer a round from a different game.')

        if self.selected_option_id is not None and self.numeric_value is not None:
            raise ValidationError('An answer cannot include both a selected option and a numeric value.')

        if self.round_id and self.round.question_type == Round.CHOICE:
            if self.selected_option_id is None and self.numeric_value is not None:
                raise ValidationError('Choice questions require a selected option, not a numeric value.')
        if self.round_id and self.round.question_type == Round.NUMERIC:
            if self.numeric_value is None and self.selected_option_id is not None:
                raise ValidationError('Numeric questions require a numeric answer, not a selected option.')

    def __str__(self):
        return f'Answer for Round {self.round.number} by {self.player.user}'
