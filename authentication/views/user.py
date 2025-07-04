from rest_framework import generics, status
from rest_framework.response import Response
from ..serializers.user import UserLoginSerializer, UserProfileSerializer, UserRegisterSerializer, UserChangePasswordSerializer
from ..models import UserSession, User
from django.middleware.csrf import get_token
import uuid
from rest_framework import status
from datetime import timedelta
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils.timezone import now
from ..utils import get_client_ip
from rest_framework.views import APIView


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
            expires_at=expires_at,
        )

        user_data = UserProfileSerializer(new_user).data

        response = Response(user_data, status=status.HTTP_201_CREATED)
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
            httponly=True,
            secure=True,  # Must be True for HTTPS
            samesite='None'  # 'None' required for cross-site cookies with credentials
        )
        csrf_token = get_token(request)
        response['X-CSRFToken'] = csrf_token
        return response

class UserLogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        sessions = UserSession.objects.filter(user_id=user)
        response = Response({'details': 'Logged out successfully'}, status=status.HTTP_200_OK)
        if sessions:
            sessions.delete()
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
        else:
            response = Response({'details': 'Invalid session token'}, status=status.HTTP_400_BAD_REQUEST)
            
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
            return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)
        return Response({"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)