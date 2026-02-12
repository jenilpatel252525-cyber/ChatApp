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

        room = await self.get_room()
        if not await self.is_user_in_room():
            await self.send(text_data=json.dumps({
                "type": "removed"
            }))
            return

        # =====================================================
        # GROUP CHAT
        # =====================================================
        if room.is_group:
            encrypted_text = data.get("encrypted_text")
            if not encrypted_text:
                return

            message = await self.create_group_message(
                encrypted_text=encrypted_text,
                key_version=room.key_version,
            )
            
            participants = await self.get_room_participants()

            for profile_id in participants:
                await self.channel_layer.group_send(
                    f"chat_{self.room_id}_user_{profile_id}",
                    {
                        "type": "chat_message",
                        "id": message.id,
                        "encrypted_text": message.encrypted_text,
                        "key_version": message.key_version,
                        "user": self.username,
                        "timestamp": message.timestamp.isoformat(),
                    },
            )

        # =====================================================
        # 1-1 CHAT
        # =====================================================
        else:
            enc_sender = data.get("encrypted_for_sender")
            enc_receiver = data.get("encrypted_for_receiver")

            if not enc_sender or not enc_receiver:
                return

            message = await self.create_private_message(
                enc_sender,
                enc_receiver,
            )

            participants = await self.get_room_participants()

            for profile_id in participants:
                await self.channel_layer.group_send(
                    f"chat_{self.room_id}_user_{profile_id}",
                    {
                        "type": "chat_message",
                        "id": message.id,
                        "encrypted_for_sender": message.encrypted_for_sender,
                        "encrypted_for_receiver": message.encrypted_for_receiver,
                        "user_id": self.profile.id,
                        "user": self.username,
                        "timestamp": message.timestamp.isoformat(),
                    }
                )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def removed(self,event):
        await self.send(text_data=json.dumps(event))
        
    async def room_key_rotated(self, event):
        """
        Handler for room.key_rotated events
        """
        await self.send(
            text_data=json.dumps({
                "type": "room.key_rotated",
                "version": event["version"],
            })
        )

    # =====================================================
    # DB helpers (ALL SAFE)
    # =====================================================

    @database_sync_to_async
    def get_profile_and_username(self):
        try:
            profile = UserProfile.objects.select_related("user").get(user=self.user)
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
    def get_room(self):
        return Room.objects.get(id=self.room_id)

    @database_sync_to_async
    def create_group_message(self, encrypted_text, key_version):
        room = Room.objects.get(id=self.room_id)
        return Message.objects.create(
            room=room,
            user=self.profile,
            encrypted_text=encrypted_text,
            key_version=key_version,
        )

    @database_sync_to_async
    def create_private_message(self, enc_sender, enc_receiver):
        room = Room.objects.get(id=self.room_id)
        return Message.objects.create(
            room=room,
            user=self.profile,
            encrypted_for_sender=enc_sender,
            encrypted_for_receiver=enc_receiver,
        )

    @database_sync_to_async
    def get_room_participants(self):
        room = Room.objects.get(id=self.room_id)
        return list(room.participants.values_list("user_id", flat=True))





class GroupConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.profile_id=await self.get_profile_id()

        if not self.user.is_authenticated:
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
                "type":"connected",
                "name":self.group_name
            }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # async def receive(self, text_data = None):
    #     data = json.loads(text_data)
    #     member_ids=data.get("ids")
    #     for id in member_ids:
    #         await self.channel_layer.group_send(
    #             f"group_list_{id}",
    #             {
    #                 "type":"notify"
    #             }
    #         )
            
    async def notify(self, event):
        await self.send(text_data=json.dumps({
            "type": "REFRESH_GROUPS"
        }))
        
    @database_sync_to_async
    def get_profile_id(self):
        try:
            profile = UserProfile.objects.select_related("user").get(user=self.user)
            return profile.id 
        except UserProfile.DoesNotExist:
            return None
        
        
        
        
        
class ContactNotifyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.profile_id=await self.get_profile_id()

        if not self.user.is_authenticated:
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
                "type":"connected",
                "name":self.group_name
            }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f"contact_list_{self.user.id}",
            self.channel_name
        )

    async def notify(self, event):
        await self.send(text_data=json.dumps({
            "type": "REFRESH_CONTACTS"
        }))
        
    @database_sync_to_async
    def get_profile_id(self):
        try:
            profile = UserProfile.objects.select_related("user").get(user=self.user)
            return profile.id 
        except UserProfile.DoesNotExist:
            return None
        