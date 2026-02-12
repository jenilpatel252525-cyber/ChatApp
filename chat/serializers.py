# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Room, Message, UserProfile, UserEncryptionKey, RoomKeyForUser

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "username", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = User(
            email=validated_data["email"],
            username=validated_data["username"],
        )
        user.set_password(validated_data["password"])
        user.save()
        UserProfile.objects.create(user=user)
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class UserProfileMiniSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = ["id", "user"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    contacts = UserProfileMiniSerializer(many=True, read_only=True)

    class Meta:
        model = UserProfile
        fields = ["id", "user", "contacts"]


class RoomSerializer(serializers.ModelSerializer):
    admin = UserProfileMiniSerializer(read_only=True)
    participants = UserProfileMiniSerializer(many=True, read_only=True)
    participant_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=UserProfile.objects.all(),
        write_only=True,
        source="participants",
    )

    class Meta:
        model = Room
        fields = [
            "id",
            "name",
            "is_group",
            "admin",
            "participants",
            "participant_ids",
            "created_at",
            "key_version",
        ]
        read_only_fields = ["created_at", "key_version"]


# serializers.py
from rest_framework import serializers
from .models import Message, Room
from .models import UserProfile


class MessageSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    # -------- GROUP --------
    encrypted_text = serializers.CharField(required=False, allow_null=True)
    key_version = serializers.IntegerField(required=False, allow_null=True)

    # -------- 1-1 --------
    encrypted_for_sender = serializers.CharField(required=False, allow_null=True)
    encrypted_for_receiver = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "room",
            "user",
            "encrypted_text",
            "encrypted_for_sender",
            "encrypted_for_receiver",
            "key_version",
            "timestamp",
        ]
        read_only_fields = ["id", "user", "timestamp"]

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "username": obj.user.user.username,
        }

class UserEncryptionKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserEncryptionKey
        fields = [
            "id",
            "public_key",
            "encrypted_private_key_backup",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def create(self, validated_data):
        user = self.context["request"].user

        defaults = {}
        if "public_key" in validated_data:
            defaults["public_key"] = validated_data["public_key"]

        if "encrypted_private_key_backup" in validated_data:
            defaults["encrypted_private_key_backup"] = validated_data[
                "encrypted_private_key_backup"
            ]

        key_obj, _ = UserEncryptionKey.objects.update_or_create(
            user=user,
            defaults=defaults,
        )
        return key_obj


class RoomKeyForUserSerializer(serializers.ModelSerializer):
    room = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all()
    )
    user = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.all()
    )

    class Meta:
        model = RoomKeyForUser
        fields = [
            "id",
            "room",
            "user",
            "encrypted_room_key",
            "version",
            "created_at",
        ]
        read_only_fields = ["created_at"]