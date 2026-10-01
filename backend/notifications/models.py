from django.conf import settings
from django.db import models

CHANNELS = [("whatsapp", "WhatsApp"), ("email", "Email"), ("push", "Web Push")]


class Trigger(models.Model):
    key = models.SlugField(unique=True)          # e.g. "login"
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Template(models.Model):
    WA_STATUS = [("draft", "Draft"), ("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")]
    trigger = models.ForeignKey(Trigger, related_name="templates", on_delete=models.CASCADE)
    channel = models.CharField(max_length=10, choices=CHANNELS)
    name = models.CharField(max_length=120, blank=True)
    subject = models.CharField(max_length=255, blank=True)   # email
    title = models.CharField(max_length=255, blank=True)     # web push
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    # WhatsApp specific
    wa_template_name = models.CharField(max_length=120, blank=True)
    wa_language = models.CharField(max_length=10, default="en_US")
    wa_status = models.CharField(max_length=10, choices=WA_STATUS, default="draft")
    wa_note = models.CharField(max_length=255, blank=True)
    # {"1": "name", "2": "order_id"} -> maps {{1}} placeholders to context variables
    variables = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("trigger", "channel")

class Country(models.Model):
    name = models.CharField(max_length=80)
    iso_code = models.CharField(max_length=3, unique=True)      # IN, US ...
    dial_code = models.CharField(max_length=6)                  # "91" (digits only, no +)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"

    def save(self, *a, **kw):
        self.dial_code = "".join(c for c in self.dial_code if c.isdigit())
        self.iso_code = self.iso_code.upper()
        super().save(*a, **kw)

    def __str__(self):
        return f"{self.name} (+{self.dial_code})"

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    country = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    phone = models.CharField(max_length=20, blank=True)  # international format, e.g. 919999999999

    @property
    def full_phone(self):
        """Digits only, with country code, e.g. 919999999999 (what WhatsApp needs)."""
        digits = "".join(c for c in self.phone if c.isdigit())
        if not digits:
            return ""
        if self.country:
            digits = digits.lstrip("0")
            if not digits.startswith(self.country.dial_code) or len(digits) <= 10:
                digits = self.country.dial_code + digits
        return digits

class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subs")
    subscription_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class NotificationLog(models.Model):
    trigger_key = models.CharField(max_length=80)
    channel = models.CharField(max_length=10)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    success = models.BooleanField(default=False)
    detail = models.TextField(blank=True)
    is_test = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
