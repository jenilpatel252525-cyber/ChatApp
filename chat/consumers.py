from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Room, Message, UserProfile
import json

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"chat_{self.room_id}_user_{self.user.id}"

        if not self.user.is_authenticated:
            await self.close()
            return

        data = await self.get_profile_and_username()
        if not data:
            await self.close()
            return

        self.profile = data["profile"]
        self.username = data["username"]

        if not await self.is_user_in_room():
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        data = json.loads(text_data)

        if not await self.is_user_in_room():
            await self.send(
                text_data=json.dumps({
                    "type": "removed"
                })
            )
            return

        text = data.get("text")

        if not text:
            return

        message = await self.create_message(text)

        participants = await self.get_room_participants()

        for user_id in participants:
            await self.channel_layer.group_send(
                f"chat_{self.room_id}_user_{user_id}",
                {
                    "type": "chat_message",
                    "id": message.id,
                    "text": message.text,
                    "user_id": self.profile.id,
                    "user": self.username,
                    "timestamp": message.timestamp.isoformat(),
                },
            )
            
    async def notify(self, event):
        await self.send(text_data=json.dumps(
            {
                "type": "REFRESH_MEMBERS"
            }
        ))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def removed(self, event):
        await self.send(text_data=json.dumps(
            {
                "type": "removed"
            }
        ))
        await self.close()
        
    async def deleted(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "deleted"
            })
        )
        await self.close()


    # ==========================================
    # Database Helpers
    # ==========================================

    @database_sync_to_async
    def get_profile_and_username(self):
        try:
            profile = UserProfile.objects.select_related("user").get(
                user=self.user
            )

            return {
                "profile": profile,
                "username": profile.user.username,
            }

        except UserProfile.DoesNotExist:
            return None

    @database_sync_to_async
    def is_user_in_room(self):
        room = Room.objects.get(id=self.room_id)
        return room.participants.filter(id=self.profile.id).exists()

    @database_sync_to_async
    def create_message(self, text):
        room = Room.objects.get(id=self.room_id)

        return Message.objects.create(
            room=room,
            user=self.profile,
            text=text,
        )

    @database_sync_to_async
    def get_room_participants(self):
        room = Room.objects.get(id=self.room_id)

        return list(
            room.participants.values_list(
                "user_id",
                flat=True,
            )
        )
        
        
        
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import UserProfile
import json


class GroupConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.profile_id = await self.get_profile_id()

        if not self.profile_id:
            await self.close()
            return

        self.group_name = f"group_list_{self.profile_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        await self.send(
            text_data=json.dumps({
                "type": "connected",
                "name": self.group_name
            })
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def notify(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "REFRESH_GROUPS"
            })
        )

    @database_sync_to_async
    def get_profile_id(self):
        try:
            profile = UserProfile.objects.select_related(
                "user"
            ).get(user=self.user)

            return profile.id

        except UserProfile.DoesNotExist:
            return None
        
        
        
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import UserProfile
import json


class ContactNotifyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.profile_id = await self.get_profile_id()

        if not self.profile_id:
            await self.close()
            return

        self.group_name = f"contact_list_{self.profile_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        await self.send(
            text_data=json.dumps({
                "type": "connected",
                "name": self.group_name
            })
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def notify(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "REFRESH_CONTACTS"
            })
        )

    @database_sync_to_async
    def get_profile_id(self):
        try:
            profile = UserProfile.objects.select_related(
                "user"
            ).get(user=self.user)

            return profile.id

        except UserProfile.DoesNotExist:
            return None