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
        related_name="admin_rooms",
        on_delete=models.CASCADE,
    )
    participants = models.ManyToManyField(
        UserProfile, related_name="participant_rooms", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_group = models.BooleanField(default=False)
    key_version = models.IntegerField(default=1)

    def __str__(self):
        return self.name


class UserEncryptionKey(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="encryption_key"
    )
    public_key = models.TextField(blank=True)
    encrypted_private_key_backup = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RoomKeyForUser(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="room_keys")
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="room_keys")
    encrypted_room_key = models.TextField()
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("room", "user", "version")
        ordering = ["-version", "-created_at"]


class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    # 1-1 only
    encrypted_for_sender = models.TextField(null=True, blank=True)
    encrypted_for_receiver = models.TextField(null=True, blank=True)

    # group only
    encrypted_text = models.TextField(null=True, blank=True)
    key_version = models.IntegerField(null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]