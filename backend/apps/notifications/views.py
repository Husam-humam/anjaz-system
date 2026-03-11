from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer
from .services import NotificationService


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_read', 'notification_type']

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        """تعليم إشعار كمقروء"""
        notification = self.get_object()
        NotificationService.mark_as_read(notification)
        return Response({'status': 'تم تعليم الإشعار كمقروء'})

    @action(detail=False, methods=['post'], url_path='read_all')
    def mark_all_read(self, request):
        """تعليم جميع الإشعارات كمقروءة"""
        NotificationService.mark_all_as_read(request.user)
        return Response({'status': 'تم تعليم جميع الإشعارات كمقروءة'})

    @action(detail=False, methods=['get'], url_path='unread_count')
    def unread_count(self, request):
        """عدد الإشعارات غير المقروءة"""
        count = NotificationService.get_unread_count(request.user)
        return Response({'count': count})
