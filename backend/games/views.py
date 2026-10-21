from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError

from auth_app.views import SessionAuthAPIView
from games.serializers import WaitingRoomSerializer
from games.services.waiting_room import join_waiting_room, leave_waiting_room


def _raise_drf_validation(exc: DjangoValidationError) -> None:
    messages = exc.messages if hasattr(exc, 'messages') else [str(exc)]
    raise DRFValidationError({'non_field_errors': messages})


class WaitingRoomJoinView(SessionAuthAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            room = join_waiting_room(request.user)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)

        room.refresh_from_db()
        return Response(
            WaitingRoomSerializer(room).data,
            status=status.HTTP_200_OK,
        )


class WaitingRoomLeaveView(SessionAuthAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        leave_waiting_room(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
