from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.auth import get_user_model

from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import (
    UserProfile,
    Room,
    Message,
    UserEncryptionKey,
    RoomKeyForUser,
)
from .serializers import (
    RegisterSerializer,
    RoomSerializer,
    MessageSerializer,
    UserProfileSerializer,
    UserEncryptionKeySerializer,
    RoomKeyForUserSerializer,
)

User = get_user_model()

# ---------------------------
# UserProfileViewSet
# ---------------------------
class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = UserProfile.objects.all()

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def add_contact(self, request):
        profile = UserProfile.objects.get(user=request.user)
        profile_id = request.data.get("profile_id")

        if not profile_id:
            return Response({"error": "profile_id is required"}, status=400)

        new_contact = get_object_or_404(UserProfile, id=profile_id)

        if new_contact == profile:
            return Response({"error": "You cannot add yourself."}, status=400)

        if profile.contacts.filter(id=new_contact.id).exists():
            return Response({"message": "Already in contacts."}, status=200)

        profile.contacts.add(new_contact)
        profile.save()
        new_contact.contacts.add(profile)
        new_contact.save()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"contact_list_{profile_id}",
            {"type": "notify"}
        )
        # async_to_sync(channel_layer.group_send)(
        #     f"contact_list_{profile_id}",
        #     {"type": "notify"}
        # )
        return Response({"message": f"{new_contact.user.username} added."}, status=200)

    @action(detail=False, methods=["post"])
    def remove_contact(self, request):
        profile = UserProfile.objects.get(user=request.user)
        profile_id = request.data.get("profile_id")

        if not profile_id:
            return Response({"error": "profile_id required"}, status=400)

        contact = get_object_or_404(UserProfile, id=profile_id)

        if not profile.contacts.filter(id=contact.id).exists():
            return Response({"error": "Not found in contacts."}, status=404)

        profile.contacts.remove(contact)
        profile.save()
        contact.contacts.remove(profile)
        contact.save()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"contact_list_{profile_id}",
            {"type": "notify"}
        )
        # async_to_sync(channel_layer.group_send)(
        #     f"contact_list_{profile_id}",
        #     {"type": "notify"}
        # )
        return Response({"message": f"{contact.user.username} removed."}, status=200)


# ---------------------------
# RegisterViewSet
# ---------------------------
class RegisterViewSet(viewsets.ModelViewSet):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    queryset = User.objects.all()

    def perform_create(self, serializer):
        user = serializer.save()
        UserProfile.objects.get_or_create(user=user)
        return user


# ---------------------------
# RoomViewSet
# ---------------------------
class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Room.objects.all()

    def get_queryset(self):
        profile = UserProfile.objects.get(user=self.request.user)
        return Room.objects.filter(
            models.Q(participants=profile) | models.Q(admin=profile)
        ).distinct()
        
        # rooms_as_participant = Room.objects.filter(participants=profile)
        # rooms_as_admin = Room.objects.filter(admin=profile)

        # return (rooms_as_participant | rooms_as_admin).distinct()
        
        # rooms = list(Room.objects.filter(participants=profile))
        # rooms += list(Room.objects.filter(admin=profile))
        # return set(rooms)

    def create(self, request):
        name = request.data.get("name")
        is_group = request.data.get("is_group", False)
        participant_ids = request.data.get("participants_ids", [])
        admin_profile = UserProfile.objects.get(user=request.user)

        if not name:
            return Response({"error": "Room name required"}, status=400)

        room = Room.objects.create(name=name, is_group=is_group, admin=admin_profile)

        for pid in participant_ids:
            try:
                participant = UserProfile.objects.get(id=pid)
                room.participants.add(participant)
            except UserProfile.DoesNotExist:
                continue

        room.participants.add(admin_profile)
        serializer = self.get_serializer(room)
        return Response(serializer.data, status=201)

    @action(detail=True, methods=["post"])
    def add_member(self, request, pk=None):
        room = self.get_object()
        profile = UserProfile.objects.get(user=request.user)

        if room.admin != profile:
            return Response(
                {"detail": "Only room admin can add members."},
                status=status.HTTP_403_FORBIDDEN,
            )
            
        channel_layer = get_channel_layer()

        participant_ids = request.data.get("participants_ids", [])
        for pid in participant_ids:
            try:
                participant = UserProfile.objects.get(id=pid)
                room.participants.add(participant)
                async_to_sync(channel_layer.group_send)(
                    f"group_list_{pid}",
                    {"type": "notify"}
                )

            except UserProfile.DoesNotExist:
                continue

        # 🔐 AUTO KEY ROTATION

        # async_to_sync(get_channel_layer().group_send)(
        #     f"chat_{room.id}",
        #     {"type": "room.key_rotated", "version": room.key_version},
        # )

        serializer = self.get_serializer(room)
        return Response(serializer.data, status=200)

    @action(detail=True, methods=["post"])
    def remove_member(self, request, pk=None):
        room = self.get_object()
        profile = UserProfile.objects.get(user=request.user)
        
        channel_layer = get_channel_layer()
        
        participant_ids = request.data.get("participants_ids", [])
        for pid in participant_ids:
            try:
                participant = UserProfile.objects.get(id=pid)
                room.participants.remove(participant)
                async_to_sync(channel_layer.group_send)(
                    f"group_list_{pid}",
                    {"type": "notify"}
                )
            except UserProfile.DoesNotExist:
                continue
        
        # async_to_sync(channel_layer.group_send)(
        #     f"chat_{room.id}_user_{room.admin.id}",
        #     {
        #         "type": "refresh",
        #     },
        # )


        # 🔐 AUTO KEY ROTATION

        # async_to_sync(get_channel_layer().group_send)(
        #     f"chat_{room.id}",
        #     {"type": "room.key_rotated", "version": room.key_version},
        # )

        serializer = self.get_serializer(room)
        return Response(serializer.data, status=200)

    @action(detail=True, methods=["post"], url_path="set-room-keys")
    def set_room_keys(self, request, pk=None):
        room = Room.objects.get(pk=pk)

        keys_data = request.data.get("keys", [])
        if not isinstance(keys_data, list) or not keys_data:
            return Response(
                {"detail": "keys list required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1️⃣ Rotate version
        room.key_version += 1
        room.save(update_fields=["key_version"])
        version = room.key_version

        created = []
        for item in keys_data:
            uid = item.get("user_profile_id")
            enc = item.get("encrypted_room_key")
            if not uid or not enc:
                continue

            try:
                target_profile = UserProfile.objects.get(id=uid)
            except UserProfile.DoesNotExist:
                continue

            if target_profile not in room.participants.all():
                continue

            obj, _ = RoomKeyForUser.objects.update_or_create(
                room=room,
                user=target_profile,
                version=version,
                defaults={"encrypted_room_key": enc},
            )
            created.append(obj.id)

        # 2️⃣ Notify EACH USER WS GROUP
        channel_layer = get_channel_layer()

        participant_user_ids = (
            room.participants
            .select_related("user")
            .values_list("user_id", flat=True)
        )

        for user_id in participant_user_ids:
            async_to_sync(channel_layer.group_send)(
                f"chat_{room.id}_user_{user_id}",
                {
                    "type": "room_key_rotated",
                    "version": version,
                },
            )

        return Response(
            {"status": "ok", "created_ids": created},
            status=200,
        )


    # @action(detail=True, methods=["post"], url_path="notify_key_rotated")
    # def notify_key_rotated(self, request, pk=None):
    #     room = self.get_object()
    #     profile = UserProfile.objects.get(user=request.user)

    #     if room.admin != profile:
    #         return Response(
    #             {"detail": "Only room admin may notify rotation."},
    #             status=status.HTTP_403_FORBIDDEN,
    #         )

    #     version = request.data.get("version", room.key_version)
    #     async_to_sync(get_channel_layer().group_send)(
    #         f"chat_{room.id}",
    #         {"type": "room.key_rotated", "version": version},
    #     )
    #     return Response({"ok": True})


# ---------------------------
# Messages
# ---------------------------
class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = UserProfile.objects.get(user=self.request.user)
        room_id = self.request.query_params.get("room_id")

        qs = Message.objects.filter(room__participants=profile)

        if room_id:
            qs = qs.filter(room_id=room_id)

        return qs.select_related("room", "user")

    def perform_create(self, serializer):
        profile = UserProfile.objects.get(user=self.request.user)
        room = get_object_or_404(Room, id=self.request.data.get("room"))

        if profile not in room.participants.all():
            raise serializers.ValidationError("Not a participant of this room.")

        # ============================
        # GROUP CHAT
        # ============================
        if room.is_group:
            encrypted_text = serializer.validated_data.get("encrypted_text")
            key_version = serializer.validated_data.get("key_version")

            if not encrypted_text:
                raise serializers.ValidationError("encrypted_text required for group")

            if key_version != room.key_version:
                raise serializers.ValidationError("Stale room key version")

            serializer.save(
                user=profile,
                room=room,
                encrypted_for_sender=None,
                encrypted_for_receiver=None,
            )
            return

        # ============================
        # 1-1 CHAT
        # ============================
        encrypted_for_sender = serializer.validated_data.get("encrypted_for_sender")
        encrypted_for_receiver = serializer.validated_data.get(
            "encrypted_for_receiver"
        )

        if not encrypted_for_sender or not encrypted_for_receiver:
            raise serializers.ValidationError(
                "Both encrypted_for_sender and encrypted_for_receiver are required"
            )

        serializer.save(
            user=profile,
            room=room,
            encrypted_text=None,
            key_version=None,
        )

# ---------------------------
# UserEncryptionKey viewset
# ---------------------------
class UserEncryptionKeyViewSet(viewsets.ModelViewSet):
    serializer_class = UserEncryptionKeySerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = UserEncryptionKey.objects.all()

    def list(self, request, *args, **kwargs):
        user_id = request.query_params.get("user_id")
        if user_id:
            qs = self.get_queryset().filter(user_id=user_id)
        else:
            qs = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        # 🔐 FORCE ownership
        serializer.save(user=self.request.user)

# ---------------------------
# RoomKeyForUser viewset
# ---------------------------
class RoomKeyForUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RoomKeyForUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = UserProfile.objects.get(user=self.request.user)
        qs = RoomKeyForUser.objects.filter(user=profile)

        room_id = self.request.query_params.get("room_id")
        version = self.request.query_params.get("version")

        if room_id:
            qs = qs.filter(room_id=room_id)
        if version:
            try:
                qs = qs.filter(version=int(version))
            except ValueError:
                pass

        return qs.order_by("-version", "-created_at")
