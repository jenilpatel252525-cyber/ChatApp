from django.contrib import admin
from .models import Room,Message,UserProfile,UserEncryptionKey,RoomKeyForUser

# Register your models here.

admin.site.register(Message)
admin.site.register(Room)
admin.site.register(UserProfile)
admin.site.register(UserEncryptionKey)
admin.site.register(RoomKeyForUser)