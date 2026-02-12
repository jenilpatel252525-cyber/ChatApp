# chat/routing.py
from django.urls import re_path
from .consumers import ChatConsumer,GroupConsumer,ContactNotifyConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_id>\d+)/$', ChatConsumer.as_asgi()),
    re_path(r'ws/contact/$', ContactNotifyConsumer.as_asgi()),
    re_path(r'ws/group/$', GroupConsumer.as_asgi()),
]