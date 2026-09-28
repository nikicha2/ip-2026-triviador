from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


AVATAR_KEYS = (
    ('knight-1', 'knight-1'),
    ('knight-2', 'knight-2'),
    ('knight-3', 'knight-3'),
    ('knight-4', 'knight-4'),
)


class User(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    nickname = models.CharField(max_length=30, unique=True)
    avatar_key = models.CharField(
        max_length=30,
        choices=AVATAR_KEYS,
        default='knight-1',
    )

    class Meta:
        verbose_name = 'profile'
        verbose_name_plural = 'profiles'

    def __str__(self):
        return self.nickname
