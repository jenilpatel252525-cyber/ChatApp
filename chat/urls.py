from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterViewSet, RoomViewSet, MessageViewSet,UserProfileViewSet

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'register', RegisterViewSet, basename='register')
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'userprofile',UserProfileViewSet,basename='userprofile')

urlpatterns = router.urls