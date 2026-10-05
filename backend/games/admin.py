from django.contrib import admin

from .models import Game, Player, Round


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
