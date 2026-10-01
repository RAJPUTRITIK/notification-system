import logging
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import viewsets, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from . import services
from .models import Trigger, Template, Profile, PushSubscription, NotificationLog, Country
from .serializers import TriggerSerializer, TemplateSerializer, LogSerializer, CountrySerializer


log = logging.getLogger("notifications")


def user_json(u):
    p = getattr(u, "profile", None)
    return {"id": u.id, "username": u.username, "email": u.email, "is_staff": u.is_staff,
            "phone": p.phone if p else "", "country": p.country_id if p else None,
            "full_phone": p.full_phone if p else "", "push_subscribed": u.push_subs.exists()}


# ---------- Auth ----------
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    d = request.data
    if not d.get("username") or not d.get("password"):
        return Response({"error": "username and password required"}, status=400)
    if User.objects.filter(username=d["username"]).exists():
        return Response({"error": "username taken"}, status=400)
    log.info("AUTH register username=%s", d["username"])
    u = User.objects.create_user(d["username"], d.get("email", ""), d["password"], first_name=d.get("first_name", ""))
    Profile.objects.create(user=u, phone=d.get("phone", ""), country_id=d.get("country") or None)
    token, _ = Token.objects.get_or_create(user=u)
    return Response({"token": token.key, "user": user_json(u)}, status=201)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    u = authenticate(username=request.data.get("username"), password=request.data.get("password"))
    if not u:
        log.warning("AUTH login failed username=%s", request.data.get("username"))
        return Response({"error": "Invalid credentials"}, status=400)
    log.info("AUTH login ok username=%s", u.username)
    Profile.objects.get_or_create(user=u)
    from django.contrib.auth.models import update_last_login
    update_last_login(None, u)
    token, _ = Token.objects.get_or_create(user=u)
    sent = services.fire("login", u)                      # TRIGGER: login
    return Response({"token": token.key, "user": user_json(u), "notifications": _summ(sent)})


@api_view(["POST"])
def logout(request):
    log.info("AUTH logout username=%s", request.user.username)
    sent = services.fire("logout", request.user)          # TRIGGER: logout
    Token.objects.filter(user=request.user).delete()
    return Response({"ok": True, "notifications": _summ(sent)})


@api_view(["GET", "PATCH"])
def me(request):
    if request.method == "PATCH":
        p, _ = Profile.objects.get_or_create(user=request.user)
        if "phone" in request.data:
            p.phone = request.data["phone"]
        if "country" in request.data:
            p.country_id = request.data["country"] or None
        p.save()
        if "email" in request.data:
            request.user.email = request.data["email"]; request.user.save()
    return Response(user_json(request.user))


@api_view(["POST"])
def push_subscribe(request):
    sid = request.data.get("subscription_id")
    if not sid:
        return Response({"error": "subscription_id required"}, status=400)
    log.info("PUSH subscribed user=%s sub=%s", request.user.username, services.mask(sid))
    PushSubscription.objects.update_or_create(subscription_id=sid, defaults={"user": request.user})
    return Response({"ok": True})


@api_view(["POST"])
def fire_event(request, key):
    """Website fires any trigger (e.g. order_placed, password_reset)."""
    if not Trigger.objects.filter(key=key).exists():
        return Response({"error": "unknown trigger"}, status=404)
    return Response({"notifications": _summ(services.fire(key, request.user, dict(request.data)))})


def _summ(res):
    return {ch: {"ok": ok, "detail": d} for ch, (ok, d) in res.items()}


# ---------- Admin APIs ----------
class TriggerViewSet(viewsets.ModelViewSet):
    queryset = Trigger.objects.prefetch_related("templates")
    serializer_class = TriggerSerializer
    permission_classes = [IsAdminUser]

    def perform_create(self, s):
        t = s.save()
        log.info("ADMIN %s created trigger key=%s", self.request.user.username, t.key)

    def perform_destroy(self, instance):
        log.warning("ADMIN %s deleted trigger key=%s", self.request.user.username, instance.key)
        instance.delete()


class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.select_related("trigger")
    serializer_class = TemplateSerializer
    permission_classes = [IsAdminUser]

    def perform_destroy(self, instance):
        log.warning("ADMIN %s deleted template id=%s (%s/%s)", self.request.user.username, instance.id, instance.trigger.key, instance.channel)
        instance.delete()

    def perform_create(self, s):
        tpl = s.save()
        log.info("ADMIN %s created template id=%s trigger=%s channel=%s", self.request.user.username, tpl.id, tpl.trigger.key, tpl.channel)
        if tpl.channel == "whatsapp":
            services.submit_wa_template(tpl)

    def perform_update(self, s):
        old_body = s.instance.body
        tpl = s.save()
        log.info("ADMIN %s updated template id=%s trigger=%s channel=%s", self.request.user.username, tpl.id, tpl.trigger.key, tpl.channel)
        if tpl.channel == "whatsapp" and tpl.body != old_body:
            import time
            tpl.wa_template_name = f"{tpl.trigger.key.replace('-', '_')}_{tpl.id}_{int(time.time())}"
            services.submit_wa_template(tpl)

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        t = self.get_object(); t.is_active = not t.is_active; t.save()
        log.info("ADMIN %s toggled template id=%s (%s/%s) -> %s", request.user.username, t.id, t.trigger.key, t.channel, "ON" if t.is_active else "OFF")
        return Response(TemplateSerializer(t).data)

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        t = self.get_object()
        if t.channel != "whatsapp":
            return Response({"error": "WhatsApp only"}, status=400)
        return Response(TemplateSerializer(services.sync_wa_template(t)).data)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        t = self.get_object()
        ok, detail = services.send_template(t, request.user, {"order_id": "TEST-1001"}, is_test=True)
        return Response({"ok": ok, "detail": detail}, status=200 if ok else 400)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def logs(request):
    qs = NotificationLog.objects.all()
    p = request.query_params
    if p.get("channel"):
        qs = qs.filter(channel=p["channel"])
    if p.get("trigger"):
        qs = qs.filter(trigger_key=p["trigger"])
    if p.get("success") in ("true", "false"):
        qs = qs.filter(success=p["success"] == "true")
    return Response(LogSerializer(qs[:200], many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def countries(request):
    """Public list used by the phone-number dropdown."""
    return Response(CountrySerializer(Country.objects.filter(is_active=True), many=True).data)


class CountryViewSet(viewsets.ModelViewSet):
    """Admin: add / edit / disable countries (shows inactive too)."""
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = [IsAdminUser]
