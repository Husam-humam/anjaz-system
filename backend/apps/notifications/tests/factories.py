"""
مصانع البيانات التجريبية لتطبيق الإشعارات.
"""
import factory

from apps.accounts.tests.factories import SectionManagerFactory
from apps.notifications.models import Notification


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    recipient = factory.SubFactory(SectionManagerFactory)
    notification_type = "period_opened"
    title = "إشعار تجريبي"
    message = "محتوى الإشعار التجريبي"
    is_read = False
    related_model = "WeeklyPeriod"
    related_id = 1
