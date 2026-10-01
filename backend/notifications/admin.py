from django.contrib import admin
from .models import *
for m in (Trigger, Template, Profile, PushSubscription, NotificationLog):
    admin.site.register(m)
