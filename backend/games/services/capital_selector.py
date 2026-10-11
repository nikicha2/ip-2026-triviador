"""
Capital selector service for finding valid capital territory assignments.

A valid capital assignment consists of three distinct, mutually non-adjacent territories.
This service finds all such valid assignments and provides random selection.
"""

import random
from typing import Callable, List, Optional, Set, Tuple

from django.core.exceptions import ValidationError

from games.map import MapDefinition


class CapitalSelector:
    """
    Selects three non-adjacent capital territories for a game.
    
    Supports random selection from all valid independent sets of size 3,
    with optional test control via a custom random selector.
    """
    
    @staticmethod
    def find_all_independent_sets(
        territory_slugs: List[str],
        adjacency_map: dict
    ) -> List[Tuple[str, str, str]]:
        """
        Find all independent sets of size 3 from the given territories.
        
        An independent set is a set of territories where no two are adjacent.
        
        Args:
            territory_slugs: List of territory slugs to consider
            adjacency_map: Dict mapping slug -> set of adjacent slugs
            
        Returns:
            List of tuples (slug1, slug2, slug3) where each tuple is an
            independent set of size 3. List is empty if no such sets exist.
        """
        result = []
        n = len(territory_slugs)
        
        # Check all combinations of 3 territories
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    slug_i = territory_slugs[i]
                    slug_j = territory_slugs[j]
                    slug_k = territory_slugs[k]
                    
                    neighbors_i = adjacency_map.get(slug_i, set())
                    neighbors_j = adjacency_map.get(slug_j, set())
                    neighbors_k = adjacency_map.get(slug_k, set())
                    
                    # Check if i, j, k form an independent set
                    if (slug_j not in neighbors_i and
                        slug_k not in neighbors_i and
                        slug_k not in neighbors_j):
                        result.append((slug_i, slug_j, slug_k))
        
        return result
    
    @staticmethod
    def select_capitals(
        random_selector: Optional[Callable] = None
    ) -> Tuple[str, str, str]:
        """
        Select three random non-adjacent capital territories from the project map.
        
        Args:
            random_selector: Optional callable for test control. If provided,
                           should accept a list and return one element.
                           Defaults to random.choice() if None.
        
        Returns:
            Tuple of three territory slugs (capital1_slug, capital2_slug, capital3_slug).
            
        Raises:
            ValidationError: If no valid capital assignment exists.
        """
        if random_selector is None:
            random_selector = random.choice
        
        # Get all territories and adjacencies from map definition
        territory_slugs = sorted(MapDefinition.get_territory_slugs())
        adjacency_map = MapDefinition.get_adjacencies()
        
        # Find all valid independent sets of size 3
        valid_sets = CapitalSelector.find_all_independent_sets(
            territory_slugs,
            adjacency_map
        )
        
        if not valid_sets:
            raise ValidationError(
                'No valid capital assignment exists for this map. '
                'Map must contain an independent set of three territories.'
            )
        
        # Randomly select one valid set
        selected_set = random_selector(valid_sets)
        return selected_set
