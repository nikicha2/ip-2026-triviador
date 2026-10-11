"""
Tests for game initialization (M05).

Covers territory creation, capital assignment, atomicity, and concurrency aspects
of the M05 game initialization feature.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import transaction

from games.models import Game, Player, Territory, Capital
from games.map import MapDefinition
from games.services.initializer import GameInitializer
from games.services.capital_selector import CapitalSelector

User = get_user_model()


class GameInitializationPreconditionsTests(TestCase):
    """Test precondition validation for game initialization."""
    
    def setUp(self):
        """Create test fixtures."""
        self.users = [
            User.objects.create_user(username='alice', email='alice@test.com', password='pass'),
            User.objects.create_user(username='bob', email='bob@test.com', password='pass'),
            User.objects.create_user(username='carol', email='carol@test.com', password='pass'),
        ]
    
    def test_initialization_requires_waiting_status(self):
        """Test that only games with status 'waiting' can be initialized."""
        game = Game.objects.create()
        for i, user in enumerate(self.users):
            Player.objects.create(
                game=game,
                user=user,
                color=[Player.RED, Player.GREEN, Player.BLUE][i]
            )
        
        # Transition to ACTIVE before initialization
        game.status = Game.Status.ACTIVE
        game.save()
        
        with self.assertRaises(ValidationError) as cm:
            game.initialize()
        
        self.assertIn('waiting', str(cm.exception).lower())
    
    def test_initialization_requires_exactly_three_players(self):
        """Test that exactly 3 players are required."""
        # Test with 1 player
        game = Game.objects.create()
        Player.objects.create(game=game, user=self.users[0], color=Player.RED)
        
        with self.assertRaises(ValidationError) as cm:
            game.initialize()
        self.assertIn('exactly 3', str(cm.exception).lower())
        
        # Test with 2 players
        game2 = Game.objects.create()
        Player.objects.create(game=game2, user=self.users[0], color=Player.RED)
        Player.objects.create(game=game2, user=self.users[1], color=Player.GREEN)
        
        with self.assertRaises(ValidationError) as cm:
            game2.initialize()
        self.assertIn('exactly 3', str(cm.exception).lower())
    
    def test_initialization_rejects_games_with_territories(self):
        """Test that games with pre-existing territories are rejected."""
        game = Game.objects.create()
        for i, user in enumerate(self.users):
            Player.objects.create(
                game=game,
                user=user,
                color=[Player.RED, Player.GREEN, Player.BLUE][i]
            )
        
        # Pre-create a territory
        Territory.objects.create(game=game, name='Test', slug='test')
        
        with self.assertRaises(ValidationError) as cm:
            game.initialize()
        
        self.assertIn('already has territories', str(cm.exception).lower())
    
    def test_initialization_rejects_games_with_capitals(self):
        """Test that games with pre-existing capitals are rejected.
        
        Note: Since the validation checks territories first, a game with
        capitals will be rejected for having territories (since capitals
        are created with territories). This test verifies the rejection
        happens with an appropriate error message.
        """
        game = Game.objects.create()
        players = []
        for i, user in enumerate(self.users):
            player = Player.objects.create(
                game=game,
                user=user,
                color=[Player.RED, Player.GREEN, Player.BLUE][i]
            )
            players.append(player)
        
        # Pre-create a territory with capital
        territory = Territory.objects.create(game=game, name='Capital', slug='capital')
        # Set territory owner before creating capital
        territory.owner = players[0]
        territory.save()
        Capital.objects.create(player=players[0], territory=territory, health=3)
        
        with self.assertRaises(ValidationError) as cm:
            game.initialize()
        
        # The error will be about territories (which capitals depend on)
        self.assertIn('already has', str(cm.exception).lower())


class GameInitializationSuccessTests(TestCase):
    """Test successful game initialization."""
    
    def setUp(self):
        """Create test fixtures."""
        self.users = [
            User.objects.create_user(username='alice', email='alice@test.com', password='pass'),
            User.objects.create_user(username='bob', email='bob@test.com', password='pass'),
            User.objects.create_user(username='carol', email='carol@test.com', password='pass'),
        ]
        
        self.game = Game.objects.create()
        self.players = []
        for i, user in enumerate(self.users):
            player = Player.objects.create(
                game=self.game,
                user=user,
                color=[Player.RED, Player.GREEN, Player.BLUE][i]
            )
            self.players.append(player)
    
    def test_successful_initialization(self):
        """Test basic successful initialization."""
        result_game = self.game.initialize()
        
        self.assertEqual(result_game.status, Game.Status.ACTIVE)
        self.assertEqual(result_game.pk, self.game.pk)
    
    def test_all_territories_created(self):
        """Test that all 18 territories are created."""
        self.game.initialize()
        
        territories = self.game.territories.all()
        self.assertEqual(territories.count(), 18)
    
    def test_territory_count_matches_map(self):
        """Test that territory count matches map definition."""
        self.game.initialize()
        
        expected_count = len(MapDefinition.TERRITORIES)
        actual_count = self.game.territories.count()
        
        self.assertEqual(actual_count, expected_count)
    
    def test_territory_names_match_map(self):
        """Test that territory names match the map definition."""
        self.game.initialize()
        
        expected_territories = MapDefinition.get_territories()
        
        for slug, expected_name in expected_territories.items():
            territory = self.game.territories.get(slug=slug)
            self.assertEqual(territory.name, expected_name)
    
    def test_territory_slugs_match_map(self):
        """Test that territory slugs match the map definition."""
        self.game.initialize()
        
        expected_slugs = MapDefinition.get_territory_slugs()
        actual_slugs = {t.slug for t in self.game.territories.all()}
        
        self.assertEqual(actual_slugs, expected_slugs)
    
    def test_all_territories_have_zero_score(self):
        """Test that all territories start with score = 0."""
        self.game.initialize()
        
        territories = self.game.territories.all()
        for territory in territories:
            self.assertEqual(territory.score, 0)
    
    def test_no_territories_have_owner_except_capitals(self):
        """Test that only capital territories have owners."""
        self.game.initialize()
        
        capital_ids = set(
            Capital.objects.filter(player__game=self.game).values_list('territory_id', flat=True)
        )
        
        territories = self.game.territories.all()
        for territory in territories:
            if territory.pk in capital_ids:
                self.assertIsNotNone(territory.owner)
            else:
                self.assertIsNone(territory.owner)
    
    def test_adjacency_relationships_correct(self):
        """Test that adjacency relationships match the map definition."""
        self.game.initialize()
        
        expected_adjacencies = MapDefinition.get_adjacencies()
        
        for slug, expected_neighbors in expected_adjacencies.items():
            territory = self.game.territories.get(slug=slug)
            actual_neighbors = {n.slug for n in territory.neighbors.all()}
            
            self.assertEqual(
                actual_neighbors,
                expected_neighbors,
                f'Adjacency mismatch for territory {slug}'
            )
    
    def test_exactly_three_capitals_created(self):
        """Test that exactly 3 capitals are created."""
        self.game.initialize()
        
        capitals = Capital.objects.filter(player__game=self.game)
        self.assertEqual(capitals.count(), 3)
    
    def test_one_capital_per_player(self):
        """Test that each player has exactly one capital."""
        self.game.initialize()
        
        for player in self.players:
            capitals = Capital.objects.filter(player=player)
            self.assertEqual(capitals.count(), 1)
    
    def test_all_capitals_have_health_three(self):
        """Test that all capitals start with health = 3."""
        self.game.initialize()
        
        capitals = Capital.objects.filter(player__game=self.game)
        for capital in capitals:
            self.assertEqual(capital.health, 3)
    
    def test_capital_territories_distinct(self):
        """Test that the three capital territories are distinct."""
        self.game.initialize()
        
        capital_territories = Capital.objects.filter(
            player__game=self.game
        ).values_list('territory_id', flat=True)
        
        self.assertEqual(len(capital_territories), 3)
        self.assertEqual(len(set(capital_territories)), 3)
    
    def test_capital_territories_non_adjacent(self):
        """Test that capital territories are pairwise non-adjacent."""
        self.game.initialize()
        
        capitals = Capital.objects.filter(player__game=self.game).select_related('territory')
        capital_territories = [cap.territory for cap in capitals]
        
        # Check each pair is non-adjacent
        for i in range(len(capital_territories)):
            for j in range(i + 1, len(capital_territories)):
                t_i = capital_territories[i]
                t_j = capital_territories[j]
                
                neighbors_i = set(t_i.neighbors.all())
                self.assertNotIn(t_j, neighbors_i,
                    f'{t_i.slug} and {t_j.slug} should not be adjacent')
    
    def test_capital_territories_owned_by_player(self):
        """Test that capital territories are owned by their respective players."""
        self.game.initialize()
        
        capitals = Capital.objects.filter(player__game=self.game)
        
        for capital in capitals:
            self.assertEqual(capital.territory.owner, capital.player)
    
    def test_player_scores_unchanged(self):
        """Test that player scores are not modified during initialization."""
        # Set specific scores
        for i, player in enumerate(self.players):
            player.score = i * 10
            player.save()
        
        self.game.initialize()
        
        for i, player in enumerate(self.players):
            player.refresh_from_db()
            self.assertEqual(player.score, i * 10)
    
    def test_no_rounds_created(self):
        """Test that no rounds are created during initialization."""
        self.game.initialize()
        
        rounds = self.game.rounds.all()
        self.assertEqual(rounds.count(), 0)
    
    def test_independent_game_territories(self):
        """Test that different games have independent territory records."""
        game1 = self.game
        game1.initialize()
        
        # Create second game
        game2 = Game.objects.create()
        users2 = [
            User.objects.create_user(username='dave', email='dave@test.com', password='pass'),
            User.objects.create_user(username='eve', email='eve@test.com', password='pass'),
            User.objects.create_user(username='frank', email='frank@test.com', password='pass'),
        ]
        for i, user in enumerate(users2):
            Player.objects.create(
                game=game2,
                user=user,
                color=[Player.RED, Player.GREEN, Player.BLUE][i]
            )
        game2.initialize()
        
        # Verify games have separate territory records
        self.assertEqual(game1.territories.count(), 18)
        self.assertEqual(game2.territories.count(), 18)
        
        game1_slugs = {t.slug for t in game1.territories.all()}
        game2_slugs = {t.slug for t in game2.territories.all()}
        
        # Slugs are the same (from map) but actual Territory instances are different
        self.assertEqual(game1_slugs, game2_slugs)
        
        game1_ids = set(game1.territories.values_list('id', flat=True))
        game2_ids = set(game2.territories.values_list('id', flat=True))
        self.assertEqual(len(game1_ids & game2_ids), 0)  # No overlap


class GameInitializationRepeatedTests(TestCase):
    """Test repeated initialization attempts."""
    
    def setUp(self):
        """Create test fixtures."""
        self.users = [
            User.objects.create_user(username='alice', email='alice@test.com', password='pass'),
            User.objects.create_user(username='bob', email='bob@test.com', password='pass'),
            User.objects.create_user(username='carol', email='carol@test.com', password='pass'),
        ]
        
        self.game = Game.objects.create()
        for i, user in enumerate(self.users):
            Player.objects.create(
                game=self.game,
                user=user,
                color=[Player.RED, Player.GREEN, Player.BLUE][i]
            )
    
    def test_repeated_initialization_rejected(self):
        """Test that re-initializing an active game is rejected."""
        self.game.initialize()
        
        # Attempt to re-initialize
        with self.assertRaises(ValidationError) as cm:
            self.game.initialize()
        
        self.assertIn('waiting', str(cm.exception).lower())
    
    def test_repeated_initialization_does_not_duplicate_territories(self):
        """Test that attempted re-initialization doesn't create duplicates."""
        self.game.initialize()
        initial_count = self.game.territories.count()
        
        # Attempt re-initialization (will fail)
        try:
            self.game.initialize()
        except ValidationError:
            pass
        
        # Verify no duplicates were created
        final_count = self.game.territories.count()
        self.assertEqual(initial_count, final_count)


class GameInitializationAtomicityTests(TransactionTestCase):
    """Test atomicity of game initialization."""
    
    def setUp(self):
        """Create test fixtures."""
        self.users = [
            User.objects.create_user(username='alice', email='alice@test.com', password='pass'),
            User.objects.create_user(username='bob', email='bob@test.com', password='pass'),
            User.objects.create_user(username='carol', email='carol@test.com', password='pass'),
        ]
        
        self.game = Game.objects.create()
        for i, user in enumerate(self.users):
            Player.objects.create(
                game=self.game,
                user=user,
                color=[Player.RED, Player.GREEN, Player.BLUE][i]
            )
    
    def test_failed_initialization_rolls_back_territories(self):
        """Test that failed initialization rolls back all territory changes."""
        # Mock GameInitializer to fail after creating territories
        original_create = GameInitializer._create_capitals
        
        def failing_create(*args, **kwargs):
            raise ValidationError('Simulated failure')
        
        try:
            GameInitializer._create_capitals = failing_create
            
            with self.assertRaises(ValidationError):
                self.game.initialize()
            
            # Verify no territories were created
            self.assertEqual(self.game.territories.count(), 0)
            
            # Verify game status is still waiting
            self.game.refresh_from_db()
            self.assertEqual(self.game.status, Game.Status.WAITING)
        finally:
            GameInitializer._create_capitals = original_create
    
    def test_failed_initialization_does_not_change_status(self):
        """Test that failed initialization doesn't change game status."""
        # Create a pre-existing territory to cause initialization to fail
        Territory.objects.create(game=self.game, name='Pre-existing', slug='pre-existing')
        
        with self.assertRaises(ValidationError):
            self.game.initialize()
        
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, Game.Status.WAITING)


class CapitalSelectorTests(TestCase):
    """Test the capital selector service."""
    
    def test_find_all_independent_sets(self):
        """Test finding all independent sets of size 3."""
        territory_slugs = sorted(MapDefinition.get_territory_slugs())
        adjacency_map = MapDefinition.get_adjacencies()
        
        sets = CapitalSelector.find_all_independent_sets(territory_slugs, adjacency_map)
        
        # Should find multiple valid sets
        self.assertGreater(len(sets), 0)
        
        # All sets should have exactly 3 elements
        for capital_set in sets:
            self.assertEqual(len(capital_set), 3)
            # All elements should be distinct
            self.assertEqual(len(set(capital_set)), 3)
    
    def test_selected_capitals_are_non_adjacent(self):
        """Test that selected capitals are non-adjacent."""
        territory_slugs = sorted(MapDefinition.get_territory_slugs())
        adjacency_map = MapDefinition.get_adjacencies()
        
        sets = CapitalSelector.find_all_independent_sets(territory_slugs, adjacency_map)
        
        for capital_set in sets:
            slug_a, slug_b, slug_c = capital_set
            neighbors_a = adjacency_map[slug_a]
            neighbors_b = adjacency_map[slug_b]
            neighbors_c = adjacency_map[slug_c]
            
            # None should be adjacent
            self.assertNotIn(slug_b, neighbors_a)
            self.assertNotIn(slug_c, neighbors_a)
            self.assertNotIn(slug_c, neighbors_b)
    
    def test_select_capitals_returns_valid_set(self):
        """Test that select_capitals returns a valid capital assignment."""
        capitals = CapitalSelector.select_capitals()
        
        self.assertEqual(len(capitals), 3)
        self.assertEqual(len(set(capitals)), 3)
        
        # Check non-adjacency
        adjacency_map = MapDefinition.get_adjacencies()
        slug_a, slug_b, slug_c = capitals
        
        neighbors_a = adjacency_map[slug_a]
        neighbors_b = adjacency_map[slug_b]
        
        self.assertNotIn(slug_b, neighbors_a)
        self.assertNotIn(slug_c, neighbors_a)
        self.assertNotIn(slug_c, neighbors_b)
    
    def test_select_capitals_with_custom_selector(self):
        """Test that custom random selector is used."""
        territory_slugs = sorted(MapDefinition.get_territory_slugs())
        adjacency_map = MapDefinition.get_adjacencies()
        
        all_sets = CapitalSelector.find_all_independent_sets(territory_slugs, adjacency_map)
        
        # Create a selector that always picks the first set
        def first_selector(lst):
            return lst[0]
        
        selected = CapitalSelector.select_capitals(random_selector=first_selector)
        
        self.assertEqual(selected, all_sets[0])
    
    def test_select_capitals_randomness(self):
        """Test that select_capitals can return different sets."""
        # This is a probabilistic test - with 18 territories and many valid sets,
        # we should get different results in most cases
        sets = set()
        for _ in range(10):
            capitals = CapitalSelector.select_capitals()
            sets.add(capitals)
        
        # Should get at least 2 different sets in 10 attempts
        self.assertGreater(len(sets), 1,
            'Capital selector should return different sets, not always the same one'
        )
