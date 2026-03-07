from django.utils import timezone
from .models import UserSession
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.authentication import BaseAuthentication

class CustomSessionAuthentication(BaseAuthentication):
    def authenticate(self, request):
        session_token = request.COOKIES.get('session_token')
        
        if not session_token:
            return None

        try:
            session = UserSession.objects.select_related('user').get(session_token=session_token)
        except UserSession.DoesNotExist:
            raise AuthenticationFailed('სესია არასწორია!')

        if session.expires_at < timezone.now():
            session.delete()
            raise AuthenticationFailed('სესიას გაუვიდა ვადა!')

        # allowed_paths = [
        #     '/api/v1/user/verify-email/', 
        #     '/api/v1/user/resend-code/',
        #     '/api/v1/user/logout/'
        # ]
        
        # if not session.user.email_verified and request.path not in allowed_paths:
        #     raise AuthenticationFailed({
        #         "detail": "გთხოვთ, ჯერ გაიაროთ მეილის ვერიფიკაცია!",
        #         "needs_verification": True
        #     })

        return (session.user, None)