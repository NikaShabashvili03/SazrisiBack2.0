from django.urls import path
from ..views.user import UserChangePassword, UserLoginView, UserProfileView, UserLogoutView, UserRegisterView

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('register/', UserRegisterView.as_view(), name="user-register"),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('logout/', UserLogoutView.as_view(), name="user-logout"),
    path('change-password/', UserChangePassword.as_view(), name="change-password")
]