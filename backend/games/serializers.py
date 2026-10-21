from rest_framework import serializers

from games.models import WaitingRoom


class WaitingRoomSerializer(serializers.ModelSerializer):
    waiting_room_id = serializers.IntegerField(source='pk', read_only=True)
    game_id = serializers.IntegerField(read_only=True)
    waiting_count = serializers.SerializerMethodField()

    class Meta:
        model = WaitingRoom
        fields = ('waiting_room_id', 'game_id', 'is_active', 'waiting_count')

    def get_waiting_count(self, obj):
        return obj.waiting.count()
