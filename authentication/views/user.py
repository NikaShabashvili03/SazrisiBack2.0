from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from django.middleware.csrf import get_token
from django.utils.timezone import now

from datetime import timedelta
import uuid
import requests

from ..serializers.user import (
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegisterSerializer,
    UserChangePasswordSerializer,
    AvatarUploadSerializer,
    AvatarSerializer,
    PreferencesCreateSerializer,
    PreferencesSerializer,
    PasswordResetSendCodeSerializer,
    PasswordResetConfirmSerializer,
)
from django.conf import settings
from ..models import UserSession, User, VerificationCode
from ..utils import get_client_ip


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


class RegisterSendCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def send_ubill_sms(self, phone, code):
        url = "https://api.ubill.dev/v1/sms/send"
        headers = {
            'key': settings.UBILL_API_KEY,
            'Content-Type': 'application/json'
        }
        payload = {
            "brandID": 1,
            "numbers": [int(phone)],
            "text": f"თქვენი ვერიფიკაციის კოდია: {code}",
            "stopList": False
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"SMS Error: {e}")
            return False

    def post(self, request):
        phone = request.data.get('phone')

        if not phone:
            return Response({"detail": "ნომერი აუცილებელია."}, status=400)

        if User.objects.filter(phone=phone).exists():
            return Response({"detail": "ეს ნომერი უკვე დაკავებულია."}, status=400)

        verification, created = VerificationCode.objects.get_or_create(phone=phone)

        if not verification.can_resend():
            return Response({"detail": "დაიცადეთ 60 წამი."}, status=429)

        verification.generate_code()
        sms_success = self.send_ubill_sms(phone, verification.code)

        if sms_success:
            return Response({"detail": "კოდი გამოგზავნილია."}, status=200)

        return Response({"detail": "ვერ მოხერხდა SMS-ის გაგზავნა."}, status=500)


class UserRegisterView(generics.GenericAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_user = serializer.save()

        token = str(uuid.uuid4())
        expires_at = now() + timedelta(days=2)

        session = UserSession.objects.create(
            user=new_user,
            session_token=token,
            ip=get_client_ip(request),
            expires_at=expires_at
        )

        response = Response(UserProfileSerializer(new_user).data, status=status.HTTP_201_CREATED)

        response.set_cookie(
            'session_token',
            session.session_token,
            expires=expires_at,
            httponly=True,
            secure=True,
            samesite='None'
        )

        return response


class UserLoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

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

        response = Response(user_data, status=status.HTTP_200_OK)

        response.set_cookie(
            'session_token',
            session.session_token,
            expires=expires_at,
            httponly=True,
            secure=True,
            samesite='None'
        )

        csrf_token = get_token(request)
        response['X-CSRFToken'] = csrf_token

        return response


class UserLogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user

        sessions = UserSession.objects.filter(user=user)

        if not sessions.exists():
            return Response({'details': 'არასწორი ტოკენი!'}, status=status.HTTP_400_BAD_REQUEST)

        sessions.delete()

        response = Response(
            {'details': 'მომხმარებლის გასვლა მოხერხდა წარმატებით!'},
            status=status.HTTP_200_OK
        )

        response.set_cookie(
            'session_token',
            value='',
            expires='Thu, 01 Jan 1970 00:00:00 GMT',
            max_age=0,
            path='/',
            httponly=True,
            secure=True,
            samesite='None'
        )

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
        serializer = UserChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "პაროლი განახლდა წარმატებით."}, status=status.HTTP_200_OK)

        return Response({"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


# =========================
# PASSWORD RESET (NEW)
# =========================

class PasswordResetSendCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def send_ubill_sms(self, phone, code):
        url = "https://api.ubill.dev/v1/sms/send"
        headers = {
            'key': settings.UBILL_API_KEY,
            'Content-Type': 'application/json'
        }
        payload = {
            "brandID": 1,
            "numbers": [int(phone)],
            "text": f"თქვენი პაროლის აღდგენის კოდია: {code}",
            "stopList": False
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"SMS Error: {e}")
            return False

    def post(self, request):
        serializer = PasswordResetSendCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]

        verification, created = VerificationCode.objects.get_or_create(phone=phone)

        if not verification.can_resend():
            return Response({"detail": "დაიცადეთ 60 წამი."}, status=429)

        verification.generate_code()

        sms_success = self.send_ubill_sms(phone, verification.code)

        if sms_success:
            return Response({"detail": "პაროლის აღდგენის კოდი გამოგზავნილია."}, status=200)

        return Response({"detail": "ვერ მოხერხდა SMS-ის გაგზავნა."}, status=500)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"detail": "პაროლი წარმატებით განახლდა."},
            status=status.HTTP_200_OK
        )