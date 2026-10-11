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

    def initialize(self, random_selector=None):
        """
        Explicitly initialize the game by creating territories and capitals.
        
        This is a separate, explicit operation that must be called to set up
        the game. It is not automatic and must not run during game creation
        or status transitions.
        
        Preconditions:
        - Game exists and has status 'waiting'
        - Game has exactly 3 players
        - Game has no territories or capitals yet
        - Map definition is valid
        
        On success:
        - Creates all 18 territories with score = 0, owner = None
        - Establishes neighbor relationships from M04 map
        - Assigns one capital to each player
        - Sets capital territories' owner to their player
        - All capitals start with health = 3
        - Game status transitions to 'active'
        
        On failure (precondition or validation error):
        - All changes are rolled back, database unchanged
        - Exception is raised with clear error message
        
        Args:
            random_selector: Optional callable for capital selection (test use only).
                           If provided, should accept a list and return one element.
                           Defaults to random.choice() if None.
        
        Returns:
            The initialized game with status = 'active'.
            
        Raises:
            ValidationError: If any precondition fails or initialization fails.
        """
        from games.services.initializer import GameInitializer
        
        return GameInitializer.initialize(self, random_selector)


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
    QUESTION_TYPE_CHOICES = [
        ('choice', 'Choice'),
        ('numeric', 'Numeric'),
    ]
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        null=True,
        blank=True,
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
            models.CheckConstraint(
                condition=(
                    models.Q(choice_question__isnull=True, numeric_question__isnull=True, question_type__isnull=True) |
                    models.Q(models.Q(choice_question__isnull=False, numeric_question__isnull=True, question_type='choice')) |
                    models.Q(models.Q(choice_question__isnull=True, numeric_question__isnull=False, question_type='numeric'))
                ),
                name='round_question_reference_matches_type',
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


class Territory(models.Model):
    """
    Represents a territory in a game, belonging to the project-wide map.
    
    Each game has its own set of Territory records conforming to the fixed
    project map definition. A territory can be owned by a player and has a score.
    Territories are connected via a many-to-many adjacency relationship.
    """
    
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='territories',
    )
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=50)
    owner = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_territories',
    )
    neighbors = models.ManyToManyField(
        'self',
        symmetrical=True,
    )
    score = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['game', 'name'],
                name='unique_territory_name_per_game',
            ),
            models.UniqueConstraint(
                fields=['game', 'slug'],
                name='unique_territory_slug_per_game',
            ),
            models.CheckConstraint(
                condition=Q(score__gte=0),
                name='territory_score_gte_0',
            ),
        ]
        ordering = ['game', 'slug']

    def __str__(self):
        return f'{self.name} (Game {self.game_id})'

    def clean(self):
        super().clean()
        
        # Validate owner belongs to the same game
        if self.owner_id is not None and self.owner.game_id != self.game_id:
            raise ValidationError(
                'Territory owner must belong to the same game.'
            )
        
        # Validate score is non-negative
        if self.score < 0:
            raise ValidationError('Territory score cannot be negative.')
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        # Always validate before saving
        self.full_clean()
        return super().save(*args, **kwargs)


class Capital(models.Model):
    """
    Represents a player's capital territory with health points.
    
    A capital is a special territory that serves as a player's stronghold.
    Each player can have at most one capital, and each territory can have
    at most one capital. Health ranges from 0 to 3.
    """
    
    territory = models.OneToOneField(
        Territory,
        on_delete=models.CASCADE,
        related_name='capital',
    )
    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name='capital',
    )
    health = models.IntegerField(default=3)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(health__gte=0) & Q(health__lte=3),
                name='capital_health_range_0_to_3',
            ),
        ]

    def __str__(self):
        return f'Capital: {self.player} at {self.territory}'

    def clean(self):
        super().clean()
        
        # Validate health is in range 0-3
        if self.health < 0 or self.health > 3:
            raise ValidationError(
                'Capital health must be between 0 and 3 (inclusive).'
            )
        
        # Validate player and territory belong to the same game
        if (self.territory_id is not None and 
            self.player_id is not None and
            self.territory.game_id != self.player.game_id):
            raise ValidationError(
                'Capital territory and player must belong to the same game.'
            )
        
        # Validate territory's owner is the same player
        if (self.territory_id is not None and 
            self.player_id is not None and
            self.territory.owner_id != self.player_id):
            raise ValidationError(
                'Territory must be owned by the capital player.'
            )
        
        # Validate player doesn't already have another capital
        if self.player_id is not None:
            existing_capital = Capital.objects.filter(
                player_id=self.player_id
            ).exclude(pk=self.pk).first()
            if existing_capital is not None:
                raise ValidationError(
                    f'Player {self.player} already has a capital at {existing_capital.territory}.'
                )
        
        # Validate territory doesn't already have another capital
        if self.territory_id is not None:
            existing_capital = Capital.objects.filter(
                territory_id=self.territory_id
            ).exclude(pk=self.pk).first()
            if existing_capital is not None:
                raise ValidationError(
                    f'Territory {self.territory} already has a capital '
                    f'for player {existing_capital.player}.'
                )
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        # Always validate before saving
        self.full_clean()
        return super().save(*args, **kwargs)
