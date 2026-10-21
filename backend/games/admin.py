from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import Game, Player, Round, Territory, Capital, WaitingRoom


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'status', 'player_count')
    list_filter = ('status',)
    list_select_related = ()

    @admin.display(description='Player count')
    def player_count(self, obj):
        return obj.players.count()


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('user', 'game', 'color', 'score')
    list_filter = ('game', 'color')
    search_fields = ('user__username', 'user__email')
    list_select_related = ('user', 'game')


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('game', 'number', 'type', 'status', 'winner', 'created_at', 'completed_at')
    list_filter = ('game', 'type', 'status')
    list_select_related = ('game', 'winner', 'winner__user')


@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ('game', 'name', 'slug', 'owner', 'score', 'neighbor_count')
    list_filter = ('game', 'owner')
    search_fields = ('name', 'slug')
    list_select_related = ('game', 'owner')
    
    fieldsets = (
        ('Game Information', {
            'fields': ('game', 'name', 'slug'),
        }),
        ('Ownership and Scoring', {
            'fields': ('owner', 'score'),
        }),
        ('Adjacency', {
            'fields': ('neighbors',),
            'description': 'Select neighboring territories. Must conform to the project map definition.',
        }),
    )
    
    filter_horizontal = ('neighbors',)
    
    @admin.display(description='Neighbors')
    def neighbor_count(self, obj):
        return obj.neighbors.count()
    
    def clean_model(self, obj):
        """Validate the territory before saving."""
        # Validate basic territory properties
        obj.full_clean()
        
        # Check neighbors conform to map definition
        if obj.pk:
            from .validators import TerritoryMapValidator
            neighbor_slugs = {n.slug for n in obj.neighbors.all()}
            is_valid, errors = TerritoryMapValidator.validate_territory_neighbors(obj, neighbor_slugs)
            if not is_valid:
                raise ValidationError(
                    'Neighbor validation failed: ' + '; '.join(errors)
                )
    
    def save_model(self, request, obj, form, change):
        """Save with validation."""
        self.clean_model(obj)
        super().save_model(request, obj, form, change)


@admin.register(Capital)
class CapitalAdmin(admin.ModelAdmin):
    list_display = ('player', 'territory', 'health', 'game')
    list_filter = ('territory__game', 'health')
    search_fields = ('player__user__username', 'territory__name')
    list_select_related = ('player', 'territory', 'territory__game')
    
    fieldsets = (
        ('Capital Assignment', {
            'fields': ('player', 'territory'),
            'description': 'Capital must be at a territory owned by the player in the same game.',
        }),
        ('Health', {
            'fields': ('health',),
            'description': 'Health must be between 0 and 3 (inclusive). Health 0 is valid but means weakened.',
        }),
    )
    
    @admin.display(description='Game')
    def game(self, obj):
        return obj.territory.game
    
    def clean_model(self, obj):
        """Validate the capital before saving."""
        obj.full_clean()
    
    def save_model(self, request, obj, form, change):
        """Save with validation."""
        self.clean_model(obj)
        super().save_model(request, obj, form, change)

@admin.register(WaitingRoom)
class WaitingRoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'game', 'is_active', 'waiting_count', 'created_at')
    list_filter = ('is_active',)
    list_select_related = ('game',)
    filter_horizontal = ('waiting',)

    @admin.display(description='Waiting')
    def waiting_count(self, obj):
        return obj.waiting.count()
