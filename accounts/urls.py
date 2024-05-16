from django.urls import path
from . import views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)


app_name = "accounts"

urlpatterns = [
    # ---------- API - api ---------- #
    path("api/login/", TokenObtainPairView.as_view(), name='login'),
    path("api/refresh/", TokenRefreshView.as_view(), name='refresh_token'),
    path("api/logout/", TokenBlacklistView.as_view(), name='logout'),

    # ---------- Web - '' ---------- #
]
