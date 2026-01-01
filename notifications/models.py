# notifications/models.py
from django.conf import settings
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

User = settings.AUTH_USER_MODEL

class Notification(models.Model):
    # WHO did it?
    actor_ct       = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    actor_id       = models.CharField(max_length=255)
    actor          = GenericForeignKey("actor_ct", "actor_id")

    # WHAT happened?
    verb           = models.CharField(max_length=255)
    description    = models.TextField(blank=True)

    # Optional: the “action_object” (e.g. the Comment itself)
    action_ct      = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                       null=True, blank=True, related_name="+")
    action_id      = models.CharField(max_length=255, blank=True, null=True)
    action_object  = GenericForeignKey("action_ct", "action_id")

    # Optional: link to a target object (e.g. the BlogPost)
    target_ct      = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                       null=True, blank=True, related_name="+")
    target_id      = models.CharField(max_length=255, blank=True, null=True)
    target         = GenericForeignKey("target_ct", "target_id")

    # WHO to notify?
    recipient      = models.ForeignKey(User, on_delete=models.CASCADE,
                                       related_name="notifications")

    # Metadata
    timestamp      = models.DateTimeField(auto_now_add=True)
    unread         = models.BooleanField(default=True)
    public         = models.BooleanField(default=False)

    # Levels (for styling or filtering)
    LEVELS = (
        ("success", "Success"),
        ("info",    "Info"),
        ("warning", "Warning"),
        ("error",   "Error"),
    )
    level          = models.CharField(max_length=10, choices=LEVELS, default="info")

    class Meta:
        ordering = ["-timestamp"]

    def mark_read(self):
        if self.unread:
            self.unread = False
            self.save(update_fields=["unread"])


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(unread=True)
    def read(self):
        return self.filter(unread=False)

Notification.objects = NotificationQuerySet.as_manager()