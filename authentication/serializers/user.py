from rest_framework import serializers
from ..models import User, Avatar, Preferences
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password as django_validate_password
import re
from ..models import UserSession

def custom_password_validator(value):
    if len(value) < 8:
        raise ValidationError("პაროლი უნდა შეიცავდეს მინიმუმ 8 სიმბოლოს.")
    if not re.search(r"[0-9]", value):
        raise ValidationError("პაროლი უნდა შეიცავდეს მინიმუმ ერთ რიცხვს.")
    if not re.search(r"[A-Za-z]", value):
        raise ValidationError("პაროლი უნდა შეიცავდეს მინიმუმ ერთ ასოს.")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise ValidationError("პაროლი უნდა შეიცავდეს მინიმუმ ერთ სპეციალურ სიმბოლოს ( მაგალითად: !@#$%^&* ).")

class UserChangePasswordSerializer(serializers.Serializer):
    prev_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_prev_password(self, value):
        user = self.context['request'].user
        if not check_password(value, user.password):
            raise serializers.ValidationError("ძველი პაროლი არასწორია!")
        return value

    def validate_new_password(self, value):
        try:
            custom_password_validator(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)

        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        UserSession.objects.filter(user=user).delete()
        return user
    
class UserRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    firstname = serializers.CharField(write_only=True)
    lastname = serializers.CharField(write_only=True)
    rePassword = serializers.CharField(write_only=True)

    def validate_email(self, email):
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("მომხმარებელი ამ ემაილით უკვე არსებობს!")
        return email
    
    def validate(self, attrs):
        if attrs['password'] != attrs['rePassword']:
            raise serializers.ValidationError({"rePassword": "პაროლები არ ემთხვევა."})
        try:
            custom_password_validator(attrs['password'])
        except ValidationError as e:
            raise serializers.ValidationError({"password": e.messages})

        return attrs

    def create(self, validated_data):
        validated_data.pop('rePassword')
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
                raise serializers.ValidationError("არასწორი ემაილი ან პაროლი!")
        except User.DoesNotExist:
            raise serializers.ValidationError("მომხმარებელი ვერ მოიძებნა!")

class AvatarUploadSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(write_only=True, required=True)

    class Meta:
        model = Avatar
        fields = ['image']

    def create(self, validated_data):
        user = self.context['request'].user
        image = validated_data.get('image')

        avatar, created = Avatar.objects.get_or_create(user=user)
        avatar.url = image
        avatar.save()
        return avatar

class PreferencesCreateSerializer(serializers.ModelSerializer):
    theme_color = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Preferences
        fields = ['theme_color']

    def create(self, validated_data):
        user = self.context['request'].user
        theme_color = validated_data.get('theme_color')

        preferences, created = Preferences.objects.get_or_create(user=user)
        preferences.theme_color = theme_color
        preferences.save()
        return preferences

class PreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Preferences
        fields = ['theme_color']

class AvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Avatar
        fields = ['url']

class UserProfileSerializer(serializers.ModelSerializer):
    avatar = AvatarSerializer()
    preferences = PreferencesSerializer()

    class Meta:
        model = User 
        fields = ['id', 'firstname', 'avatar', 'preferences', 'lastname', 'email', 'email_verified']
