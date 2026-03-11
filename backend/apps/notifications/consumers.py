import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from urllib.parse import parse_qs
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Authenticate via token query parameter
        query_string = self.scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]

        if not token:
            await self.close()
            return

        user = await self.get_user_from_token(token)
        if not user:
            await self.close()
            return

        self.user = user
        self.group_name = f'notifications_user_{user.id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def notification_message(self, event):
        """Send notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['data']
        }, ensure_ascii=False))

    @database_sync_to_async
    def get_user_from_token(self, token_str):
        try:
            token = AccessToken(token_str)
            User = get_user_model()
            return User.objects.get(id=token['user_id'])
        except Exception:
            return None
