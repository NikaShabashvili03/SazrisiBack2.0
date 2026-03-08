from rest_framework import serializers
from ..models import User, Avatar, Preferences, VerificationCode
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password as django_validate_password
import re
from django.db.models import Q
from django.utils.timezone import now

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
        return user
    
class UserRegisterSerializer(serializers.Serializer):
    firstname = serializers.CharField()
    lastname = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)
    rePassword = serializers.CharField(write_only=True)
    verification_code = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "ემაილი უკვე დაკავებულია."})
        if User.objects.filter(phone=attrs['phone']).exists():
            raise serializers.ValidationError({"phone": "ტელეფონის ნომერი უკვე დაკავებულია."})
        
        if attrs['password'] != attrs['rePassword']:
            raise serializers.ValidationError({"rePassword": "პაროლები არ ემთხვევა."})

        try:
            v_record = VerificationCode.objects.get(phone=attrs['phone'])
            if not v_record.is_valid():
                raise serializers.ValidationError({"verification_code": "კოდს გაუვიდა ვადა."})
            
            if v_record.code != attrs['verification_code']:
                v_record.attempts_count += 1
                v_record.save()
                raise serializers.ValidationError({"verification_code": "კოდი არასწორია."})
        except VerificationCode.DoesNotExist:
            raise serializers.ValidationError({"verification_code": "ვერიფიკაციის კოდი არ მოიძებნა."})

        return attrs

    def create(self, validated_data):
        validated_data.pop('rePassword')
        code = validated_data.pop('verification_code')
      
        user = User.objects.create(**validated_data)
        user.phone_verified = now()
        user.save()
        
        VerificationCode.objects.filter(phone=user.phone).delete()
        return user
    
class UserLoginSerializer(serializers.Serializer):
    login_id = serializers.CharField() 
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        login_id = data.get('login_id')
        password = data.get('password')

        try:
            user = User.objects.get(Q(email=login_id) | Q(phone=login_id))
            
            if user.check_password(password):
                return user
            raise serializers.ValidationError("არასწორი პაროლი!")
            
        except User.DoesNotExist:
            raise serializers.ValidationError("მომხმარებელი ამ მონაცემებით ვერ მოიძებნა!")

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
        fields = ['id', 'firstname', 'lastname', 'email', 'phone', 'phone_verified', 'avatar', 'preferences']
