from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Q
from django.utils import timezone
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
    RoomMembership
)
from .serializers import (
    RegisterSerializer,
    RoomSerializer,
    MessageSerializer,
    UserProfileSerializer
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

        channel_layer = get_channel_layer()
        
        for pid in participant_ids:
            try:
                participant = UserProfile.objects.get(id=pid)

                room.participants.add(participant)

                RoomMembership.objects.create(
                    room=room,
                    user=participant
                )
                
                async_to_sync(channel_layer.group_send)(
                    f"group_list_{pid}",
                    {"type": "notify"}
                )

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
                RoomMembership.objects.create(
                    room=room,
                    user=participant
                )
                room.participants.add(participant)
                async_to_sync(channel_layer.group_send)(
                    f"group_list_{pid}",
                    {"type": "notify"}
                )

            except UserProfile.DoesNotExist:
                continue
            
        participants = room.participants.all()
        
        for p in participants:
            async_to_sync(channel_layer.group_send)(
                    f"chat_{room.id}_user_{p.user.id}",
                    {"type": "notify"}
                )

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

                membership = RoomMembership.objects.filter(
                    room=room,
                    user=participant,
                    left_at__isnull=True
                ).last()

                if membership:
                    membership.left_at = timezone.now()
                    membership.save()
                    
                async_to_sync(channel_layer.group_send)(
                    f"group_list_{pid}",
                    {"type": "notify"}
                )
                
                async_to_sync(channel_layer.group_send)(
                    f"chat_{room.id}_user_{participant.user.id}",
                    {
                        "type": "removed"
                    }
                )
                
            except UserProfile.DoesNotExist:
                continue
            
        participants = room.participants.all()
        
        for p in participants:
            async_to_sync(channel_layer.group_send)(
                    f"chat_{room.id}_user_{p.user.id}",
                    {"type": "notify"}
                )

        serializer = self.get_serializer(room)
        return Response(serializer.data, status=200)
    
    def destroy(self, request, *args, **kwargs):
        room = self.get_object()
        participants = room.participants.all()
        channel_layer = get_channel_layer()
        for p in participants:
            async_to_sync(channel_layer.group_send)(
                    f"group_list_{p.id}",
                    {"type": "notify"}
                )
            async_to_sync(channel_layer.group_send)(
                        f"chat_{room.id}_user_{p.user.id}",
                        {
                            "type": "deleted"
                        }
                    )
        room.delete()


# ---------------------------
# Messages
# ---------------------------
class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = UserProfile.objects.get(user=self.request.user)

        room_id = self.request.query_params.get("room_id")

        memberships = RoomMembership.objects.filter(
            user=profile
        )

        query = Q()

        if room_id:
            memberships = memberships.filter(room_id=room_id)

        for membership in memberships:

            if membership.left_at:
                query |= Q(
                    room=membership.room,
                    timestamp__gte=membership.joined_at,
                    timestamp__lte=membership.left_at,
                )
            else:
                query |= Q(
                    room=membership.room,
                    timestamp__gte=membership.joined_at,
                )

        return Message.objects.filter(query).select_related(
            "room",
            "user"
        )
        
    def perform_create(self, serializer):
        profile = UserProfile.objects.get(user=self.request.user)

        room = get_object_or_404(
            Room,
            id=self.request.data.get("room")
        )

        if profile not in room.participants.all():
            raise serializers.ValidationError(
                "Not a participant of this room."
            )

        serializer.save(
            user=profile,
            room=room,
        )