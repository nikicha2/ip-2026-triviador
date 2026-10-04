from django.contrib import admin

from .models import Game, GamePlayer, Round, RoundAnswer


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_by', 'status', 'created_at', 'started_at', 'finished_at')
    list_filter = ('status',)
    search_fields = ('created_by__username', 'created_by__email')
    list_select_related = ('created_by',)


@admin.register(GamePlayer)
class GamePlayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'game', 'user', 'player_order', 'score', 'is_active')
    list_filter = ('is_active', 'game__status')
    search_fields = ('user__username', 'user__email', 'game__id')
    list_select_related = ('game', 'user')


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('id', 'game', 'number', 'status', 'question_type')
    list_filter = ('status', 'question_type')
    search_fields = ('game__id',)
    list_select_related = ('game',)


@admin.register(RoundAnswer)
class RoundAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'round', 'player', 'selected_option', 'numeric_value', 'is_correct', 'points_awarded', 'submitted_at')
    list_filter = ('is_correct', 'points_awarded', 'submitted_at')
    search_fields = ('player__user__username', 'round__game__id')
    list_select_related = ('round', 'player', 'player__user', 'selected_option')
