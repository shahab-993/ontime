# notifications/utils.py
import datetime
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from .models import Notification

User = get_user_model()

def notify_send(actor, recipient=None, verb="",
                action_object=None, target=None,
                level="info", description="", public=False,
                timestamp=None, **kwargs):
    """
    Create Notification(s).
    - If public=True, ignore `recipient` and send to all active Users.
    - Otherwise `recipient` can be a single User or an iterable of Users.
    """
    # default timestamp to now
    if timestamp is None:
        timestamp = datetime.datetime.now()

    # determine final recipient list
    if public:
        users = User.objects.filter(is_active=True)
    else:
        # allow passing a single User or iterable
        if recipient is None:
            raise ValueError("notify_send: recipient must be set when public=False")
        if hasattr(recipient, "__iter__") and not isinstance(recipient, str):
            users = recipient
        else:
            users = [recipient]

    def _make(user):
        notif = Notification(
            recipient=user,
            verb=verb,
            description=description,
            level=level,
            public=public,
            timestamp=timestamp,
        )
        # actor
        a_ct = ContentType.objects.get_for_model(actor)
        notif.actor_ct = a_ct
        notif.actor_id = str(actor.pk)
        # action_object
        if action_object is not None:
            ao_ct = ContentType.objects.get_for_model(action_object)
            notif.action_ct = ao_ct
            notif.action_id = str(action_object.pk)
        # target
        if target is not None:
            t_ct = ContentType.objects.get_for_model(target)
            notif.target_ct = t_ct
            notif.target_id = str(target.pk)
        notif.save()
        return notif

    # build & save a Notification for each user
    return [_make(u) for u in users]
