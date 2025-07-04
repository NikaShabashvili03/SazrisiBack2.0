from rest_framework import serializers
from ..models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password

class UserChangePasswordSerializer(serializers.Serializer):
    prev_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_prev_password(self, value):
        user = self.context['request'].user.user
        if not  check_password(value, user.password):
            raise serializers.ValidationError("Previous password is incorrect.")
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def save(self, **kwargs):
        user = self.context['request'].user.user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
    
class UserRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    firstname = serializers.CharField(write_only=True)
    lastname = serializers.CharField(write_only=True)

    def validate_email(self, email):
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def create(self, validated_data):
        user = User.objects.create(
            email=validated_data['email'],
            password=validated_data['password'],
            firstname=validated_data['firstname'],
            lastname=validated_data['lastname'],
        )
        return user
    
class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        try:
            user = User.objects.get(email=data['email'])
            if user.check_password(data['password']):
                return user
            else:
                raise serializers.ValidationError("Invalid credentials")
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")
        
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User 
        fields = ['id', 'firstname', 'lastname', 'email', 'email_verified']