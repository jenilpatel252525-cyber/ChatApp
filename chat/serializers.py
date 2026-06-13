# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Room, Message, UserProfile

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
        ]
        read_only_fields = ["created_at"]

class MessageSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "room",
            "user",
            "text",
            "timestamp",
        ]

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "username": obj.user.user.username,
        }