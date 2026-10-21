from django.urls import path

from .views import WaitingRoomJoinView, WaitingRoomLeaveView

app_name = 'games'

urlpatterns = [
    path('waiting-room/join/', WaitingRoomJoinView.as_view(), name='waiting_room_join'),
    path('waiting-room/leave/', WaitingRoomLeaveView.as_view(), name='waiting_room_leave'),
]
