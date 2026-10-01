import os
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from notifications.models import Trigger, Template, Profile

TRIGGERS = [
    ("login", "Login", "User signs in on the website"),
    ("logout", "Logout", "User signs out"),
    ("not_logged_in_1_day", "Not logged in 1 day", "User has not visited for 24 hours"),
    ("not_logged_in_1_week", "Not logged in 1 week", "User has not visited for 7 days"),
    ("password_reset", "Password reset", "User asks to reset password"),
    ("order_placed", "Order placed", "User completes a purchase"),
]
DEFAULTS = {
    "login": ("Welcome back, {{name}}!", "You logged in successfully"),
    "logout": ("Goodbye {{name}}, see you soon!", "You have been logged out"),
}


class Command(BaseCommand):
    help = "Create default triggers, sample templates and the admin user"

    def handle(self, *a, **kw):
        for key, name, desc in TRIGGERS:
            Trigger.objects.get_or_create(key=key, defaults={"name": name, "description": desc})
        for key, (body, subject) in DEFAULTS.items():
            t = Trigger.objects.get(key=key)
            Template.objects.get_or_create(trigger=t, channel="whatsapp", defaults=dict(
                name=f"{key}-wa", body="Hi {{1}}, " + subject + ".", variables={"1": "name"},
                wa_status="approved", wa_note="adminusercreate (sandbox)"))
            Template.objects.get_or_create(trigger=t, channel="email", defaults=dict(
                name=f"{key}-email", subject=subject, body=f"Hi {{{{name}}}},\n\n{subject}."))
            Template.objects.get_or_create(trigger=t, channel="push", defaults=dict(
                name=f"{key}-push", title=body, body=subject))
        u, created = User.objects.get_or_create(username=os.getenv("ADMIN_USERNAME", "admin"), defaults={
            "email": os.getenv("ADMIN_EMAIL", "admin@example.com"), "is_staff": True, "is_superuser": True})
        if created:
            u.set_password(os.getenv("ADMIN_PASSWORD", "admin12345")); u.save()
        Profile.objects.get_or_create(user=u)
        self.stdout.write(self.style.SUCCESS("Admin user created complete"))
