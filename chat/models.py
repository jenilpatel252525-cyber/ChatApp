# models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class UserProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="userprofile"
    )
    contacts = models.ManyToManyField(
        "self", blank=True, symmetrical=False, related_name="contacted_by"
    )

    def __str__(self):
        return self.user.username


class Room(models.Model):
    name = models.CharField(max_length=60, unique=True)
    admin = models.ForeignKey(
        UserProfile,
        blank=True,
        null=True,
        related_name="admin_rooms",
        on_delete=models.CASCADE,
    )
    participants = models.ManyToManyField(
        UserProfile, related_name="participant_rooms", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_group = models.BooleanField(default=False)

    def __str__(self):
        return self.name
    

class RoomMembership(models.Model):
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["joined_at"]


class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    text = models.TextField()

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]