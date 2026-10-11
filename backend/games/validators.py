"""
Territory and Capital validation service.

Provides reusable validation for territory conformance to the project map definition,
adjacency graph integrity, and capital eligibility.
"""

from typing import List, Tuple, Optional
from django.core.exceptions import ValidationError

from .map import MapDefinition


class TerritoryMapValidator:
    """Validates territories and adjacency relationships against the map definition."""
    
    @staticmethod
    def validate_game_territories(game) -> Tuple[bool, List[str]]:
        """
        Validate that all territories in a game conform to the map definition.
        
        Checks that:
        - The game has exactly the territories defined in MapDefinition
        - Territory names and slugs match
        - Adjacency relationships are correct
        
        Args:
            game: A Game instance
            
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        territories = game.territories.all()
        
        # Check all required territories exist
        expected_slugs = MapDefinition.get_territory_slugs()
        actual_slugs = {t.slug for t in territories}
        
        missing_slugs = expected_slugs - actual_slugs
        if missing_slugs:
            errors.append(
                f'Game is missing territories: {", ".join(sorted(missing_slugs))}'
            )
        
        extra_slugs = actual_slugs - expected_slugs
        if extra_slugs:
            errors.append(
                f'Game has extra territories: {", ".join(sorted(extra_slugs))}'
            )
        
        # Create a lookup map
        territory_map = {t.slug: t for t in territories}
        
        # Check names match
        expected_territories = MapDefinition.get_territories()
        for slug, name in expected_territories.items():
            if slug in territory_map:
                if territory_map[slug].name != name:
                    errors.append(
                        f'Territory {slug} has name "{territory_map[slug].name}" '
                        f'but expected "{name}"'
                    )
        
        # Check adjacencies match the map definition
        expected_adjacencies = MapDefinition.get_adjacencies()
        for slug, expected_neighbors in expected_adjacencies.items():
            if slug not in territory_map:
                continue
            
            territory = territory_map[slug]
            actual_neighbor_slugs = {n.slug for n in territory.neighbors.all()}
            
            missing_neighbors = expected_neighbors - actual_neighbor_slugs
            if missing_neighbors:
                errors.append(
                    f'Territory {slug} is missing neighbors: {", ".join(sorted(missing_neighbors))}'
                )
            
            extra_neighbors = actual_neighbor_slugs - expected_neighbors
            if extra_neighbors:
                errors.append(
                    f'Territory {slug} has extra neighbors: {", ".join(sorted(extra_neighbors))}'
                )
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_territory_slug(slug: str) -> bool:
        """Check if a territory slug is valid in the map definition."""
        return MapDefinition.is_territory_valid(slug)
    
    @staticmethod
    def validate_territory_neighbors(territory, neighbor_slugs: set) -> Tuple[bool, List[str]]:
        """
        Validate that a territory's neighbors conform to the map definition.
        
        Args:
            territory: A Territory instance
            neighbor_slugs: Set of neighbor territory slugs
            
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        if territory.slug not in MapDefinition.get_territory_slugs():
            errors.append(f'Territory slug "{territory.slug}" is not defined in the map.')
            return False, errors
        
        expected_neighbors = MapDefinition.get_neighbors(territory.slug)
        
        missing = expected_neighbors - neighbor_slugs
        if missing:
            errors.append(
                f'Missing neighbors for {territory.slug}: {", ".join(sorted(missing))}'
            )
        
        extra = neighbor_slugs - expected_neighbors
        if extra:
            errors.append(
                f'Invalid neighbors for {territory.slug}: {", ".join(sorted(extra))}'
            )
        
        return len(errors) == 0, errors
    
    @staticmethod
    def add_neighbors_safely(territory, neighbor_territories) -> None:
        """
        Add neighbors to a territory, validating against the map definition.
        
        This is the validated entry point for establishing adjacency relationships.
        Ensures no duplicates and maintains symmetry.
        
        Args:
            territory: A Territory instance (must be saved)
            neighbor_territories: List/queryset of Territory instances
            
        Raises:
            ValidationError: If neighbors violate map definition or graph rules
        """
        if territory.pk is None:
            raise ValidationError('Territory must be saved before adding neighbors.')
        
        neighbor_slugs = {n.slug for n in neighbor_territories}
        
        # Validate against map definition
        is_valid, errors = TerritoryMapValidator.validate_territory_neighbors(
            territory, neighbor_slugs
        )
        if not is_valid:
            raise ValidationError(
                'Invalid neighbors: ' + '; '.join(errors)
            )
        
        # Validate all neighbors belong to the same game
        for neighbor in neighbor_territories:
            if neighbor.game_id != territory.game_id:
                raise ValidationError(
                    f'Neighbor {neighbor.slug} belongs to a different game.'
                )
            
            if neighbor.pk == territory.pk:
                raise ValidationError('A territory cannot be its own neighbor.')
        
        # Clear existing neighbors and add new ones
        # The symmetrical=True ManyToMany will handle reverse relationships
        territory.neighbors.set(neighbor_territories)
    
    @staticmethod
    def check_independent_set_exists(game) -> Tuple[bool, Optional[List[str]]]:
        """
        Check if the game's territories contain an independent set of 3.
        
        This is required for capital eligibility (3 players need 3 non-adjacent capitals).
        
        Args:
            game: A Game instance
            
        Returns:
            (exists, example_set_or_none)
        """
        territories = list(game.territories.prefetch_related('neighbors').all())
        
        if len(territories) < 3:
            return False, None
        
        # Check all combinations of 3 territories
        n = len(territories)
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    t_i, t_j, t_k = territories[i], territories[j], territories[k]
                    
                    # Check if they form an independent set
                    neighbors_i = {n.pk for n in t_i.neighbors.all()}
                    neighbors_j = {n.pk for n in t_j.neighbors.all()}
                    neighbors_k = {n.pk for n in t_k.neighbors.all()}
                    
                    if (t_j.pk not in neighbors_i and
                        t_k.pk not in neighbors_i and
                        t_k.pk not in neighbors_j):
                        return True, [t_i.slug, t_j.slug, t_k.slug]
        
        return False, None
