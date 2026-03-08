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

        if not session.user.phone_verified:
             raise AuthenticationFailed({"detail": "საჭიროა ტელეფონის ვერიფიკაცია!", "needs_verification": True})

        return (session.user, None)