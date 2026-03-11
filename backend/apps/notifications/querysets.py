from django.db import models


class NotificationQuerySet(models.QuerySet):

    def unread(self):
        return self.filter(is_read=False)

    def for_user(self, user):
        return self.filter(recipient=user)
