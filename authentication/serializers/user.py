from rest_framework import serializers
from ..models import User, Avatar, Preferences, VerificationCode
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
from django.db.models import Q
from django.utils.timezone import now
import re


def custom_password_validator(value):
    if len(value) < 8:
        raise ValidationError("პაროლი უნდა შეიცავდეს მინიმუმ 8 სიმბოლოს.")
    if not re.search(r"[0-9]", value):
        raise ValidationError("პაროლი უნდა შეიცავდეს მინიმუმ ერთ რიცხვს.")
    if not re.search(r"[A-Za-z]", value):
        raise ValidationError("პაროლი უნდა შეიცავდეს მინიმუმ ერთ ასოს.")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise ValidationError("პაროლი უნდა შეიცავდეს მინიმუმ ერთ სპეციალურ სიმბოლოს (მაგალითად: !@#$%^&*).")


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
        user.save(update_fields=["password"])
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
        phone = attrs['phone']
        email = attrs['email']
        password = attrs['password']
        re_password = attrs['rePassword']
        verification_code = attrs['verification_code']

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "ემაილი უკვე დაკავებულია."})

        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError({"phone": "ტელეფონის ნომერი უკვე დაკავებულია."})

        if password != re_password:
            raise serializers.ValidationError({"rePassword": "პაროლები არ ემთხვევა."})

        try:
            custom_password_validator(password)
        except ValidationError as e:
            raise serializers.ValidationError({"password": e.messages})

        try:
            v_record = VerificationCode.objects.get(
                phone=phone,
                purpose=VerificationCode.PURPOSE_REGISTER,
            )
        except VerificationCode.DoesNotExist:
            raise serializers.ValidationError({"verification_code": "ვერიფიკაციის კოდი არ მოიძებნა."})

        if not v_record.expires_at or v_record.expires_at < now():
            raise serializers.ValidationError({"verification_code": "კოდს გაუვიდა ვადა."})

        if not v_record.is_valid(verification_code):
            raise serializers.ValidationError({"verification_code": "კოდი არასწორია."})

        attrs["verification_obj"] = v_record
        return attrs

    def create(self, validated_data):
        validated_data.pop('rePassword')
        validated_data.pop('verification_code')
        verification = validated_data.pop('verification_obj')
        password = validated_data.pop('password')

        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.phone_verified = now()
        user.save(update_fields=["password", "phone_verified", "firstname", "lastname", "email", "phone"])

        verification.mark_used()
        verification.delete()

        return user


class UserLoginSerializer(serializers.Serializer):
    login_id = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        login_id = data.get('login_id')
        password = data.get('password')

        try:
            user = User.objects.get(Q(email=login_id) | Q(phone=login_id))
        except User.DoesNotExist:
            raise serializers.ValidationError("მომხმარებელი ამ მონაცემებით ვერ მოიძებნა!")

        if not user.check_password(password):
            raise serializers.ValidationError("არასწორი პაროლი!")

        return user


class PasswordResetSendCodeSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value):
        if not User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("მომხმარებელი ამ ნომრით ვერ მოიძებნა.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    phone = serializers.CharField()
    verification_code = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    rePassword = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = attrs.get("phone")
        verification_code = attrs.get("verification_code")
        new_password = attrs.get("new_password")
        re_password = attrs.get("rePassword")

        if new_password != re_password:
            raise serializers.ValidationError({"rePassword": "პაროლები არ ემთხვევა."})

        try:
            custom_password_validator(new_password)
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": e.messages})

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError({"phone": "მომხმარებელი ვერ მოიძებნა."})

        try:
            v_record = VerificationCode.objects.get(
                phone=phone,
                purpose=VerificationCode.PURPOSE_RESET,
            )
        except VerificationCode.DoesNotExist:
            raise serializers.ValidationError({"verification_code": "ვერიფიკაციის კოდი არ მოიძებნა."})

        if not v_record.expires_at or v_record.expires_at < now():
            raise serializers.ValidationError({"verification_code": "კოდს გაუვიდა ვადა."})

        if not v_record.is_valid(verification_code):
            raise serializers.ValidationError({"verification_code": "კოდი არასწორია."})

        attrs["user_obj"] = user
        attrs["verification_obj"] = v_record
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user_obj"]
        verification = self.validated_data["verification_obj"]

        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])

        verification.mark_used()
        verification.delete()

        return user


class AvatarUploadSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(write_only=True, required=True)

    class Meta:
        model = Avatar
        fields = ['image']

    def create(self, validated_data):
        user = self.context['request'].user
        image = validated_data.get('image')

        avatar, _ = Avatar.objects.get_or_create(user=user)
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

        preferences, _ = Preferences.objects.get_or_create(user=user)
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
    avatar = serializers.SerializerMethodField()
    preferences = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'firstname',
            'lastname',
            'email',
            'phone',
            'phone_verified',
            'avatar',
            'preferences'
        ]

    def get_avatar(self, obj):
        if hasattr(obj, "avatar") and obj.avatar:
            return AvatarSerializer(obj.avatar).data
        return None

    def get_preferences(self, obj):
        if hasattr(obj, "preferences") and obj.preferences:
            return PreferencesSerializer(obj.preferences).data
        return None