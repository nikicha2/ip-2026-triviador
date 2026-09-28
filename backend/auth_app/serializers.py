from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers

from .models import Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('nickname', 'avatar_key')


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'profile')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)
    nickname = serializers.CharField(max_length=30)

    class Meta:
        model = User
        fields = ('username', 'email', 'nickname', 'password', 'password_confirm')

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('User with this username already exists.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('User with this email already exists.')
        return value

    def validate(self, attrs):
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        nickname = attrs.get('nickname')

        if password != password_confirm:
            raise serializers.ValidationError({'password_confirm': ['Passwords do not match.']})

        if Profile.objects.filter(nickname=nickname).exists():
            raise serializers.ValidationError({'nickname': ['User with this nickname already exists.']})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        nickname = validated_data.pop('nickname')
        password = validated_data.pop('password')
        validated_data.pop('password_confirm')

        user = User.objects.create_user(password=password, **validated_data)
        Profile.objects.create(user=user, nickname=nickname)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        user = authenticate(request=self.context.get('request'), username=username, password=password)
        if user is None:
            raise serializers.ValidationError({'non_field_errors': ['Invalid credentials.']})

        attrs['user'] = user
        return attrs


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('nickname', 'avatar_key')

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
