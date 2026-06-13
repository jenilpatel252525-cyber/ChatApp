from django.urls import path
from .consumers import (
    ChatConsumer,
    GroupConsumer,
    ContactNotifyConsumer,
)

websocket_urlpatterns = [
    path(
        "ws/chat/<int:room_id>/",
        ChatConsumer.as_asgi(),
    ),
    path(
        "ws/group/",
        GroupConsumer.as_asgi(),
    ),
    path(
        "ws/contact/",
        ContactNotifyConsumer.as_asgi(),
    ),
]