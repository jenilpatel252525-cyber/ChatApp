from urllib.parse import parse_qs
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async

@database_sync_to_async
def get_user(token):
    try:
        access_token = AccessToken(token)
        user = access_token.payload.get('user_id')
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.get(id=user)
    except Exception:
        return AnonymousUser()

class TokenAuthMiddleware:
    """
    Custom middleware that takes JWT from query string (?token=...)
    and attaches user to scope['user']
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token")
        if token:
            scope["user"] = await get_user(token[0])
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)
