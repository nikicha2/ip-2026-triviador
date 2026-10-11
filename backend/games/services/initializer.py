"""
Game initialization service.

Handles explicit, atomic game initialization including:
- Territory creation with map validation
- Adjacency relationship establishment
- Capital assignment and creation
- Status transition from 'waiting' to 'active'
"""

from typing import Callable, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction

from games.map import MapDefinition
from games.models import Capital, Game, Player, Territory
from games.services.capital_selector import CapitalSelector
from games.validators import TerritoryMapValidator


class GameInitializer:
    """
    Initializes a game by creating territories, neighbors, and capitals.
    
    The initialization is atomic: all changes are rolled back if any step fails.
    A game can only be initialized once, and only when waiting with exactly 3 players.
    """
    
    @staticmethod
    @transaction.atomic
    def initialize(
        game: Game,
        random_selector: Optional[Callable] = None
    ) -> Game:
        """
        Initialize a game by creating territories and assigning capitals.
        
        Preconditions:
        - Game exists and has status 'waiting'
        - Game has exactly 3 players
        - Game has no territories or capitals yet
        - Map definition is valid
        - Map has an independent set of size 3
        
        Process:
        1. Validate all preconditions
        2. Validate map definition
        3. Create all territories with score = 0 and owner = None
        4. Establish all adjacency relationships
        5. Select 3 non-adjacent territories as capitals
        6. Create capital records with health = 3, one per player
        7. Set capital territories' owners to their players
        8. Transition game status to 'active'
        
        Args:
            game: The Game instance to initialize (must be saved)
            random_selector: Optional callable for capital selection (for tests).
                           If None, uses random.choice().
        
        Returns:
            The initialized game with status = 'active'.
            
        Raises:
            ValidationError: If any precondition fails or if any step fails.
                           All database changes are rolled back on failure.
        """
        # Lock the game to prevent concurrent initialization
        game = Game.objects.select_for_update().get(pk=game.pk)
        
        # 1. Validate preconditions
        GameInitializer._validate_preconditions(game)
        
        # 2. Validate map definition
        is_valid, errors = MapDefinition.validate_map()
        if not is_valid:
            raise ValidationError(
                f'Map definition is invalid. Cannot initialize game. Errors: '
                f'{"; ".join(errors)}'
            )
        
        # 3. Create all territories with initial state
        territories = GameInitializer._create_territories(game)
        
        # 4. Establish adjacency relationships
        GameInitializer._establish_neighbors(game, territories)
        
        # 5. Select and assign capitals
        capital_slugs = GameInitializer._select_capitals(random_selector)
        
        # 6. Create capital records and ownership
        GameInitializer._create_capitals(game, territories, capital_slugs)
        
        # 7. Transition game status to active
        game.status = Game.Status.ACTIVE
        game.save(update_fields=['status'])
        
        return game
    
    @staticmethod
    def _validate_preconditions(game: Game) -> None:
        """
        Validate that the game is ready for initialization.
        
        Raises:
            ValidationError: If any precondition fails.
        """
        # Check status
        if game.status != Game.Status.WAITING:
            raise ValidationError(
                f'Game must have status "waiting" to initialize. '
                f'Current status: {game.status}'
            )
        
        # Check player count
        player_count = game.players.count()
        if player_count != 3:
            raise ValidationError(
                f'Game must have exactly 3 players to initialize. '
                f'Current player count: {player_count}'
            )
        
        # Check no pre-existing territories or capitals
        territory_count = game.territories.count()
        if territory_count > 0:
            raise ValidationError(
                f'Game already has territories (count: {territory_count}). '
                f'Cannot initialize a partially or fully initialized game.'
            )
        
        capital_count = Capital.objects.filter(
            player__game=game
        ).count()
        if capital_count > 0:
            raise ValidationError(
                f'Game already has capitals (count: {capital_count}). '
                f'Cannot initialize a partially or fully initialized game.'
            )
    
    @staticmethod
    def _create_territories(game: Game) -> dict:
        """
        Create all territories for the game from the map definition.
        
        All territories start with:
        - score = 0
        - owner = None
        
        Args:
            game: The game to create territories for.
            
        Returns:
            Dict mapping slug -> Territory instance.
        """
        territories_data = MapDefinition.get_territories()
        created_territories = {}
        
        for slug, name in territories_data.items():
            territory = Territory.objects.create(
                game=game,
                name=name,
                slug=slug,
                score=0,
                owner=None,
            )
            created_territories[slug] = territory
        
        return created_territories
    
    @staticmethod
    def _establish_neighbors(game: Game, territories: dict) -> None:
        """
        Establish adjacency relationships between territories.
        
        Uses the map definition's adjacency data to set up all neighbor
        relationships. The symmetrical ManyToMany field automatically maintains
        bidirectional relationships.
        
        Args:
            game: The game (for validation).
            territories: Dict mapping slug -> Territory instance.
            
        Raises:
            ValidationError: If neighbors don't conform to map definition.
        """
        adjacencies = MapDefinition.get_adjacencies()
        
        for slug, neighbor_slugs in adjacencies.items():
            territory = territories[slug]
            neighbor_territories = [
                territories[neighbor_slug]
                for neighbor_slug in neighbor_slugs
            ]
            
            # Use the validator's method to safely add neighbors
            TerritoryMapValidator.add_neighbors_safely(
                territory,
                neighbor_territories
            )
    
    @staticmethod
    def _select_capitals(
        random_selector: Optional[Callable] = None
    ) -> Tuple[str, str, str]:
        """
        Select three non-adjacent territories as capitals.
        
        Args:
            random_selector: Optional callable for test control.
            
        Returns:
            Tuple of three territory slugs.
            
        Raises:
            ValidationError: If no valid assignment exists.
        """
        return CapitalSelector.select_capitals(random_selector)
    
    @staticmethod
    def _create_capitals(
        game: Game,
        territories: dict,
        capital_slugs: Tuple[str, str, str]
    ) -> None:
        """
        Create capital records and establish ownership.
        
        Assigns exactly one capital to each of the three players.
        Capital territories are owned by their respective players.
        All capitals start with health = 3.
        
        Args:
            game: The game.
            territories: Dict mapping slug -> Territory instance.
            capital_slugs: Tuple of (slug1, slug2, slug3) for the three capitals.
            
        Raises:
            ValidationError: If capitals are not distinct or capital creation fails.
        """
        # Get all three players
        players = list(game.players.all())
        if len(players) != 3:
            raise ValidationError(
                f'Expected 3 players but found {len(players)}'
            )
        
        # Create one capital per player
        for player, capital_slug in zip(players, capital_slugs):
            capital_territory = territories[capital_slug]
            
            # Set territory owner to this player
            capital_territory.owner = player
            capital_territory.save(update_fields=['owner'])
            
            # Create capital record
            Capital.objects.create(
                player=player,
                territory=capital_territory,
                health=3,
            )
