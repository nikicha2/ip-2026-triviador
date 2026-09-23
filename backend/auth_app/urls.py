from django.urls import path
from .views import CustomAuthToken

app_name = 'auth_app'

urlpatterns = [
    path('login/', CustomAuthToken.as_view(), name='login'),
]
