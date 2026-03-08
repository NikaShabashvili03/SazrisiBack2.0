from django.urls import path
from ..views.user import UserChangePassword, UserLoginView, UserProfileView, UserLogoutView, UserRegisterView, AvatarView, PreferencesView, RegisterSendCodeView

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('register/send-code/', RegisterSendCodeView.as_view(), name='register-send-code'),
    path('register/', UserRegisterView.as_view(), name="user-register"),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('logout/', UserLogoutView.as_view(), name="user-logout"),
    path('avatar/', AvatarView.as_view(), name='avatar'),
    path('preferences/', PreferencesView.as_view(), name='preferences'),
    path('change-password/', UserChangePassword.as_view(), name="change-password"),
]