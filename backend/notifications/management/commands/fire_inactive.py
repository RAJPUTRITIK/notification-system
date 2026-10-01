"""Run daily (cron / Render cron job): python manage.py fire_inactive"""
import logging
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from notifications import services
from notifications.models import NotificationLog

log = logging.getLogger("notifications")
RULES = [("not_logged_in_1_week", timedelta(days=7)), ("not_logged_in_1_day", timedelta(days=1))]


class Command(BaseCommand):
    def handle(self, *a, **kw):
        now = timezone.now()
        for user in User.objects.filter(is_active=True, last_login__isnull=False):
            for key, delta in RULES:  # week first; a user only gets the longest matching trigger
                if user.last_login <= now - delta:
                    if not NotificationLog.objects.filter(user=user, trigger_key=key, created_at__gt=user.last_login).exists():
                        services.fire(key, user)
                        log.info("CRON inactive trigger=%s user=%s last_login=%s", key, user.username, user.last_login)
                        self.stdout.write(f"fired {key} for {user.username}")
                    break
