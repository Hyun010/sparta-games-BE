from django.urls import path
from . import views


app_name = "users"

urlpatterns = [
    # ---------- API---------- #
    path("api/<int:user_pk>/", views.ProfileAPIView.as_view(), name="profile"),
    path("api/user-tech-list/", views.user_tech_list, name="user_tech_list"),
    path("api/<int:user_pk>/nickname/", views.check_nickname, name="check_nickname"),
    path("api/<int:user_pk>/password/", views.change_password, name="change_password"),
    path("api/<int:user_pk>/games/", views.my_games, name="my_games"),
    path("api/<int:user_pk>/likes/", views.like_games, name="like_games"),
    
    # ---------- Web---------- #
    # path("<int:user_pk>/", views.profile_page, name='profile_page'),
]
