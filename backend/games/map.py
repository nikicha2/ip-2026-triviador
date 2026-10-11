"""
Project-wide territory map definition for Triviador.

This module defines the immutable, project-wide map structure. Each game's
Territory records should conform to this definition. Map validation ensures
graph properties required for gameplay.
"""

from typing import Dict, Set, List, Tuple


class MapDefinition:
    """
    Immutable definition of the project's territory map.
    
    Defines the complete adjacency graph, territory names and slugs,
    and provides validation utilities.
    """
    
    # Define territories: {slug: name}
    TERRITORIES = {
        'skali': 'Скали',
        'dunaviya': 'Дунавия',
        'zhitno-pole': 'Житно поле',
        'leventa': 'Левента',
        'balkania': 'Балкания',
        'tsarevo': 'Царево',
        'madara': 'Мадара',
        'pelikania': 'Пеликания',
        'kaliakra': 'Калиакра',
        'sredets': 'Средец',
        'ezera': 'Езера',
        'pirina': 'Пирина',
        'rozova-dolina': 'Розова долина',
        'chuden-kray': 'Чуден край',
        'zlaten-grozd': 'Златен грозд',
        'kukeri': 'Кукери',
        'karakachan': 'Каракачан',
        'slanchevo': 'Слънчево',
    }
    
    ADJACENCIES = {
        'skali': {'dunaviya', 'madara', 'zhitno-pole'},
        'dunaviya': {'skali', 'madara', 'zhitno-pole'},
        'madara': {'skali', 'dunaviya', 'kaliakra', 'zhitno-pole'},
        'kaliakra': {'madara', 'pelikania', 'sredets'},
        'pelikania': {'kaliakra', 'tsarevo', 'sredets'},
        'tsarevo': {'pelikania', 'sredets', 'ezera', 'slanchevo'},
        'zhitno-pole': {'skali', 'dunaviya', 'madara', 'balkania', 'sredets'},
        'sredets': {'kaliakra', 'pelikania', 'tsarevo', 'zhitno-pole', 'balkania', 'ezera', 'chuden-kray'},
        'balkania': {'zhitno-pole', 'sredets', 'ezera', 'pirina', 'rozova-dolina'},
        'ezera': {'tsarevo', 'sredets', 'balkania', 'pirina', 'chuden-kray'},
        'pirina': {'balkania', 'ezera', 'rozova-dolina', 'karakachan'},
        'rozova-dolina': {'balkania', 'pirina', 'karakachan', 'kukeri', 'zlaten-grozd'},
        'chuden-kray': {'sredets', 'ezera', 'kukeri', 'slanchevo', 'leventa'},
        'kukeri': {'rozova-dolina', 'chuden-kray', 'leventa', 'karakachan', 'slanchevo', 'zlaten-grozd'},
        'karakachan': {'pirina', 'rozova-dolina', 'kukeri', 'leventa'},
        'leventa': {'chuden-kray', 'kukeri', 'karakachan', 'slanchevo'},
        'slanchevo': {'tsarevo', 'chuden-kray', 'leventa', 'kukeri'},
        'zlaten-grozd': {'rozova-dolina', 'kukeri'},
    }
    
    @classmethod
    def get_territories(cls) -> Dict[str, str]:
        """Return the map of territory slug -> name."""
        return cls.TERRITORIES.copy()
    
    @classmethod
    def get_adjacencies(cls) -> Dict[str, Set[str]]:
        """Return the adjacency map (deep copy for safety)."""
        return {slug: neighbors.copy() for slug, neighbors in cls.ADJACENCIES.items()}
    
    @classmethod
    def get_territory_names(cls) -> Set[str]:
        """Return all territory names."""
        return set(cls.TERRITORIES.values())
    
    @classmethod
    def get_territory_slugs(cls) -> Set[str]:
        """Return all territory slugs."""
        return set(cls.TERRITORIES.keys())
    
    @classmethod
    def validate_map(cls) -> Tuple[bool, List[str]]:
        """
        Validate the map definition against all required rules.
        
        Returns:
            (is_valid, error_messages) where error_messages is a list of
            validation failures (empty if valid).
        """
        errors = []
        
        # 1. Check territory count is in allowed range and divisible by 3
        territory_count = len(cls.TERRITORIES)
        allowed_counts = {9, 12, 15, 18, 21}
        if territory_count not in allowed_counts:
            errors.append(
                f'Territory count {territory_count} not in allowed set {allowed_counts}.'
            )
        if territory_count % 3 != 0:
            errors.append(
                f'Territory count {territory_count} is not divisible by 3.'
            )
        
        # 2. Check names and slugs are unique and non-empty
        slugs = list(cls.TERRITORIES.keys())
        names = list(cls.TERRITORIES.values())
        
        for slug in slugs:
            if not slug or not isinstance(slug, str):
                errors.append(f'Invalid slug: {repr(slug)}')
        
        for name in names:
            if not name or not isinstance(name, str):
                errors.append(f'Invalid name: {repr(name)}')
        
        if len(set(slugs)) != len(slugs):
            errors.append('Duplicate territory slugs detected.')
        
        if len(set(names)) != len(names):
            errors.append('Duplicate territory names detected.')
        
        # 3. Check every adjacency references a defined territory
        for slug, neighbors in cls.ADJACENCIES.items():
            if slug not in cls.TERRITORIES:
                errors.append(f'Adjacency references undefined territory: {slug}')
            
            for neighbor_slug in neighbors:
                if neighbor_slug not in cls.TERRITORIES:
                    errors.append(
                        f'Territory {slug} is adjacent to undefined territory: {neighbor_slug}'
                    )
        
        # 4. Check no territory is adjacent to itself
        for slug, neighbors in cls.ADJACENCIES.items():
            if slug in neighbors:
                errors.append(f'Territory {slug} is adjacent to itself.')
        
        # 5. Check adjacencies are symmetric and no duplicates
        for slug, neighbors in cls.ADJACENCIES.items():
            for neighbor in neighbors:
                if slug not in cls.ADJACENCIES.get(neighbor, set()):
                    errors.append(
                        f'Adjacency not symmetric: {slug} -> {neighbor}, '
                        f'but {neighbor} does not list {slug}.'
                    )
            
            if len(neighbors) != len(set(neighbors)):
                errors.append(f'Territory {slug} has duplicate neighbors.')
        
        # 6. Check every territory has at least 2 neighbors
        for slug, neighbors in cls.ADJACENCIES.items():
            if len(neighbors) < 2:
                errors.append(
                    f'Territory {slug} has {len(neighbors)} neighbors, '
                    f'but at least 2 are required.'
                )
        
        # 7. Check graph connectivity (DFS from first territory)
        if cls.TERRITORIES:
            visited = set()
            start_slug = next(iter(cls.TERRITORIES.keys()))
            
            def dfs(slug):
                visited.add(slug)
                for neighbor in cls.ADJACENCIES.get(slug, set()):
                    if neighbor not in visited:
                        dfs(neighbor)
            
            dfs(start_slug)
            
            if len(visited) != len(cls.TERRITORIES):
                unreachable = set(cls.TERRITORIES.keys()) - visited
                errors.append(
                    f'Graph is not connected. Unreachable territories from {start_slug}: '
                    f'{unreachable}'
                )
        
        # 8. Check for independent set of size 3 (capital eligibility)
        independent_set_exists = cls._has_independent_set_of_size_3()
        if not independent_set_exists:
            errors.append(
                'Map does not contain an independent set of size 3. '
                'Cannot assign valid capitals.'
            )
        
        return len(errors) == 0, errors
    
    @classmethod
    def _has_independent_set_of_size_3(cls) -> bool:
        """
        Check if the graph contains an independent set of size 3.
        
        An independent set is a set of territories where no two are adjacent.
        Returns True if at least one such set exists.
        """
        slugs = list(cls.TERRITORIES.keys())
        n = len(slugs)
        
        # Check all combinations of 3 territories
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    slug_i, slug_j, slug_k = slugs[i], slugs[j], slugs[k]
                    
                    # Check if i, j, k form an independent set
                    neighbors_i = cls.ADJACENCIES.get(slug_i, set())
                    neighbors_j = cls.ADJACENCIES.get(slug_j, set())
                    neighbors_k = cls.ADJACENCIES.get(slug_k, set())
                    
                    if (slug_j not in neighbors_i and
                        slug_k not in neighbors_i and
                        slug_k not in neighbors_j):
                        return True
        
        return False
    
    @classmethod
    def is_territory_valid(cls, slug: str) -> bool:
        """Check if a territory slug is defined in the map."""
        return slug in cls.TERRITORIES
    
    @classmethod
    def get_territory_name(cls, slug: str) -> str:
        """Get the name for a territory slug."""
        return cls.TERRITORIES.get(slug, '')
    
    @classmethod
    def get_neighbors(cls, slug: str) -> Set[str]:
        """Get the set of neighbor slugs for a territory."""
        return cls.ADJACENCIES.get(slug, set()).copy()


def validate_map_definition():
    """
    Validate the project map definition at module load time.
    
    Raises:
        ValueError: If the map definition is invalid.
    """
    is_valid, errors = MapDefinition.validate_map()
    if not is_valid:
        raise ValueError(
            'Invalid map definition:\n' + '\n'.join(f'  - {err}' for err in errors)
        )


# Validate the map definition when this module is imported
validate_map_definition()
