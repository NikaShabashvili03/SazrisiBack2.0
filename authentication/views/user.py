from rest_framework import generics, status
from rest_framework.response import Response
from ..serializers.user import UserLoginSerializer, UserProfileSerializer, UserRegisterSerializer, UserChangePasswordSerializer, AvatarUploadSerializer, AvatarSerializer, PreferencesCreateSerializer, PreferencesSerializer, VerifyEmailSerializer
from ..models import UserSession, User, VerificationCode
from django.middleware.csrf import get_token
import uuid
from rest_framework import status
from datetime import timedelta
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils.timezone import now
from ..utils import get_client_ip
from rest_framework.views import APIView

class AvatarView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AvatarUploadSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            avatar = serializer.save()

            avatar_data = AvatarSerializer(avatar).data

            return Response(avatar_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PreferencesView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PreferencesCreateSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            preferences = serializer.save()

            preferences_data = PreferencesSerializer(preferences).data

            return Response(preferences_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class UserRegisterView(generics.GenericAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_user = serializer.save()

        verification = VerificationCode.objects.create(user=new_user)
        verification.generate_code()
        
        print(f"DEBUG: Code for {new_user.email} is {verification.code}")

        token = str(uuid.uuid4())
        expires_at = now() + timedelta(days=2)

        session = UserSession.objects.create(
            user=new_user,
            session_token=token,
            ip=get_client_ip(request),
            expires_at=expires_at,
        )

        user_data = UserProfileSerializer(new_user).data

        response = Response(user_data, status=status.HTTP_201_CREATED)
        response.set_cookie(
            'session_token',
            session.session_token,
            expires=expires_at,
            httponly=False,
            secure=True, 
            samesite='None' 
        )
        csrf_token = get_token(request)
        response['X-CSRFToken'] = csrf_token

        return response

class UserLoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        csrf_token = get_token(request)
        
        user = serializer.validated_data

        token = str(uuid.uuid4())
        user.last_login = now()
        user.save()

        expires_at = now() + timedelta(days=2)

        session = UserSession.objects.create(
            user=user,
            session_token=token,
            ip=get_client_ip(request),
            expires_at=expires_at,
        )
        
        user_data = UserProfileSerializer(user).data
        
        response = Response(user_data, status=status.HTTP_201_CREATED)
        response.set_cookie(
            'session_token',
            session.session_token,
            expires=expires_at,
            httponly=False,
            secure=True, 
            samesite='None' # samesite='Lax' 
        )
        csrf_token = get_token(request)
        response['X-CSRFToken'] = csrf_token
        return response

class UserLogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        sessions = UserSession.objects.filter(user_id=user)
        response = Response({'details': 'მომხმარებლის გასვლა მოხერხდა წარმატებით!'}, status=status.HTTP_200_OK)
        if sessions:
            # sessions.delete()
            response.set_cookie(
                'session_token',  
                value='',  
                expires='Thu, 01 Jan 1970 00:00:00 GMT',
                max_age=0,
                path='/',
                httponly=False,
                secure=True,  
                samesite='None' # samesite='Lax' 
            )
        else:
            response = Response({'details': 'არასწორი ტოკენი!'}, status=status.HTTP_400_BAD_REQUEST)
            
        return response

class UserProfileView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer
    
    def get(self, request, *args, **kwargs):
        user = request.user

        serializer = UserProfileSerializer(user)

        return Response(serializer.data)

class UserChangePassword(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = UserChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "პაროლი განახლდა წარმატებით."}, status=status.HTTP_200_OK)
        return Response({"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

class VerifyEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        
        # Check if already verified
        if user.email_verified:
            return Response({"detail": "ემაილი უკვე ვერიფიცირებულია."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            verification = user.verification_code
        except VerificationCode.DoesNotExist:
            return Response({"detail": "ვერიფიკაციის ჩანაწერი ვერ მოიძებნა."}, status=status.HTTP_404_NOT_FOUND)

        # 1. Reset attempt count if it's a new calendar day
        verification.reset_if_new_day()

        # 2. Check if daily limit (3 attempts) is exceeded
        if verification.attempts_count >= 3:
            return Response(
                {"detail": "დღიური ლიმიტი (3 მცდელობა) ამოწურულია. სცადეთ ხვალ."}, 
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        serializer = VerifyEmailSerializer(data=request.data)
        if serializer.is_valid():
            incoming_code = serializer.validated_data['code']

            # 3. Check if code is correct and not expired
            if verification.is_valid() and verification.code == incoming_code:
                user.email_verified = now()
                user.save()
                verification.delete() # Clean up after success
                return Response({"detail": "ემაილი წარმატებით ვერიფიცირდა!"}, status=status.HTTP_200_OK)

        # 4. Handle failure: Increment attempt counter
        verification.attempts_count += 1
        verification.last_attempt_at = now()
        verification.save()

        remaining = 3 - verification.attempts_count
        return Response({
            "detail": f"კოდი არასწორია. დაგრჩათ {remaining} მცდელობა."
        }, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        
        if user.email_verified:
            return Response({"detail": "ემაილი უკვე ვერიფიცირებულია."}, status=status.HTTP_400_BAD_REQUEST)

        verification, created = VerificationCode.objects.get_or_create(user=user)

        verification.reset_if_new_day()
        if verification.attempts_count >= 3:
            return Response({"detail": "ლიმიტი ამოწურულია. სცადეთ ხვალ."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        if not created and not verification.can_resend():
            return Response({"detail": f"გთხოვთ დაიცადოთ 60 წამი."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        verification.generate_code()
        
        print(f"DEBUG: New code sent: {verification.code}")

        return Response({"detail": "ახალი კოდი გამოგზავნილია მეილზე."}, status=status.HTTP_200_OK)