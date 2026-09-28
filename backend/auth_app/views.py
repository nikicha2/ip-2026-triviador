from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, MeSerializer, RegisterSerializer, UserSerializer


class SessionAuthAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def authentication_failed(self, exc):
        raise exc

    def permission_denied(self, request, message=None, code=None):
        if not request.user or not request.user.is_authenticated:
            raise AuthenticationFailed('Authentication credentials were not provided.')
        raise PermissionDenied(message or 'You do not have permission to perform this action.')

    def handle_exception(self, exc):
        if isinstance(exc, AuthenticationFailed):
            return Response({'errors': {'non_field_errors': [str(exc.detail)]}}, status=status.HTTP_401_UNAUTHORIZED)

        if isinstance(exc, PermissionDenied):
            return Response({'errors': {'non_field_errors': [str(exc.detail)]}}, status=status.HTTP_403_FORBIDDEN)

        if isinstance(exc, ValidationError):
            detail = exc.detail
            if isinstance(detail, dict):
                errors = detail
            elif isinstance(detail, list):
                errors = {'non_field_errors': detail}
            else:
                errors = {'non_field_errors': [str(detail)]}
            return Response({'errors': errors}, status=getattr(exc, 'status_code', status.HTTP_400_BAD_REQUEST))
        return super().handle_exception(exc)


class CsrfView(SessionAuthAPIView):
    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request, *args, **kwargs):
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(SessionAuthAPIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(SessionAuthAPIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(SessionAuthAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(SessionAuthAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        serializer = MeSerializer(request.user.profile, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

