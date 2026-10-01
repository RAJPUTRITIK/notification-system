"""Provider integrations + dispatcher."""
import logging
import re
import requests
from django.conf import settings
from .models import Template, NotificationLog, PushSubscription

log = logging.getLogger("notifications")
TIMEOUT = 20


def mask(v):
    """Hide sensitive recipient data in logs: 919999999999 -> 91********99, a@b.com -> a***@b.com"""
    v = str(v or "")
    if "@" in v:
        name, _, dom = v.partition("@")
        return f"{name[:1]}***@{dom}"
    return v if len(v) <= 4 else f"{v[:2]}{'*' * (len(v) - 4)}{v[-2:]}"
VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def build_context(user, extra=None):
    ctx = {"name": user.first_name or user.username, "username": user.username, "email": user.email}
    ctx.update(extra or {})
    return ctx


def render(text, ctx):
    return VAR.sub(lambda m: str(ctx.get(m.group(1), "")), text or "")


def render_wa(text, variables, ctx):
    """{{1}} -> ctx[variables['1']] ; {{name}} -> ctx['name']"""
    return VAR.sub(lambda m: str(ctx.get(variables.get(m.group(1), m.group(1)), "")), text or "")


# ---------------- WhatsApp ----------------
GRAPH = "https://graph.facebook.com/v20.0"


def _wa_headers():
    return {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}


def send_whatsapp(tpl, phone, ctx):
    if not phone:
        raise ValueError("User has no phone number")
    to = re.sub(r"\D", "", phone)
    url = f"{GRAPH}/{settings.PHONE_NUMBER_ID}/messages"
    if tpl.wa_status == "approved" and tpl.wa_template_name:
        params = [{"type": "text", "text": str(ctx.get(v, ""))}
                  for _, v in sorted(tpl.variables.items(), key=lambda kv: int(kv[0]))]
        template = {"name": tpl.wa_template_name, "language": {"code": tpl.wa_language}}
        if params:
            template["components"] = [{"type": "body", "parameters": params}]
        payload = {"messaging_product": "whatsapp", "to": to, "type": "template", "template": template}
    else:  # sandbox fallback: free-form text (works inside 24h window for test recipients)
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text",
                   "text": {"body": render_wa(tpl.body, tpl.variables, ctx)}}
    log.debug("WhatsApp -> to=%s type=%s", mask(to), payload["type"])
    r = requests.post(url, json=payload, headers=_wa_headers(), timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(f"WhatsApp {r.status_code}: {r.text[:300]}")
    return r.text[:200]


def submit_wa_template(tpl):
    """Create the template at Meta (if WABA id configured) else auto-approve in sandbox mode."""
    if not tpl.wa_template_name:
        tpl.wa_template_name = f"{tpl.trigger.key.replace('-', '_')}_{tpl.id}_v1"
    if not settings.WHATSAPP_BUSINESS_ACCOUNT_ID:
        log.info("WA template %s auto-approved (sandbox mode)", tpl.wa_template_name)
        tpl.wa_status = "approved"
        tpl.wa_note = "Sandbox mode: no WABA id set, sending as free-form text."
        tpl.save()
        return tpl
    examples = [ctx for ctx in tpl.variables.values()]
    body = {"name": tpl.wa_template_name, "language": tpl.wa_language, "category": "UTILITY",
            "components": [{"type": "BODY", "text": tpl.body}]}
    if tpl.variables:
        body["components"][0]["example"] = {"body_text": [[f"sample_{e}" for e in examples]]}
    r = requests.post(f"{GRAPH}/{settings.WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates",
                      json=body, headers=_wa_headers(), timeout=TIMEOUT)
    log.info("WA template submit name=%s status_code=%s", tpl.wa_template_name, r.status_code)
    if r.ok:
        tpl.wa_status = "pending"
        tpl.wa_note = "Submitted to Meta. Click Sync until approved."
    else:
        tpl.wa_status = "rejected"
        tpl.wa_note = r.text[:250]
    tpl.save()
    return tpl


def sync_wa_template(tpl):
    if not settings.WHATSAPP_BUSINESS_ACCOUNT_ID:
        return tpl
    r = requests.get(f"{GRAPH}/{settings.WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates",
                     params={"name": tpl.wa_template_name}, headers=_wa_headers(), timeout=TIMEOUT)
    if r.ok and r.json().get("data"):
        status = r.json()["data"][0].get("status", "").lower()
        log.info("WA template sync name=%s status=%s", tpl.wa_template_name, status)
        tpl.wa_status = status if status in ("approved", "pending", "rejected") else "pending"
        tpl.wa_note = f"Meta status: {status}"
        tpl.save()
    else:
        tpl.wa_note = f"Sync failed: {r.text[:200]}"
        tpl.save()
    return tpl


# ---------------- Email ----------------
def send_email(tpl, to_email, ctx):
    if not to_email:
        raise ValueError("User has no email")
    log.debug("Email(%s) -> to=%s", settings.EMAIL_PROVIDER, mask(to_email))
    subject, html = render(tpl.subject, ctx), render(tpl.body, ctx).replace("\n", "<br>")
    p = settings.EMAIL_PROVIDER
    if p == "postmark":
        r = requests.post("https://api.postmarkapp.com/email", timeout=TIMEOUT,
                          headers={"X-Postmark-Server-Token": settings.POSTMARKAPP_TOKEN, "Accept": "application/json"},
                          json={"From": settings.POSTMARK_FROM_EMAIL, "To": to_email, "Subject": subject,
                                "HtmlBody": html, "MessageStream": "outbound"})
    elif p == "brevo":
        r = requests.post("https://api.brevo.com/v3/smtp/email", timeout=TIMEOUT,
                          headers={"api-key": settings.BREVO_API_KEY},
                          json={"sender": {"email": settings.BREVO_FROM_EMAIL}, "to": [{"email": to_email}],
                                "subject": subject, "htmlContent": html})
    elif p == "resend":
        r = requests.post("https://api.resend.com/emails", timeout=TIMEOUT,
                          headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                          json={"from": settings.RESEND_FROM_EMAIL, "to": [to_email], "subject": subject, "html": html})
    else:
        raise ValueError(f"Unknown EMAIL_PROVIDER '{p}'")
    if not r.ok:
        raise RuntimeError(f"Email({p}) {r.status_code}: {r.text[:300]}")
    return r.text[:200]


# ---------------- Web Push (OneSignal) ----------------
def send_push(tpl, sub_ids, ctx):
    if not sub_ids:
        raise ValueError("User has no push subscription (enable push in the browser first)")
    log.debug("Push -> %d subscription(s)", len(sub_ids))
    r = requests.post("https://api.onesignal.com/notifications?c=push", timeout=TIMEOUT,
                      headers={"Authorization": f"Key {settings.ONESIGNAL_REST_API_KEY}", "Content-Type": "application/json"},
                      json={"app_id": settings.ONESIGNAL_APP_ID, "target_channel": "push",
                            "include_subscription_ids": sub_ids,
                            "headings": {"en": render(tpl.title, ctx)}, "contents": {"en": render(tpl.body, ctx)}})
    if not r.ok:
        raise RuntimeError(f"OneSignal {r.status_code}: {r.text[:300]}")
    return r.text[:200]


# ---------------- Dispatcher ----------------
def send_template(tpl, user, extra=None, is_test=False):
    ctx = build_context(user, extra)
    log.info("SEND start trigger=%s channel=%s user=%s test=%s", tpl.trigger.key, tpl.channel, user.username, is_test)
    try:
        if tpl.channel == "whatsapp":
            phone = getattr(getattr(user, "profile", None), "full_phone", "")
            detail = send_whatsapp(tpl, phone, ctx)
        elif tpl.channel == "email":
            detail = send_email(tpl, user.email, ctx)
        else:
            ids = list(PushSubscription.objects.filter(user=user).values_list("subscription_id", flat=True))
            detail = send_push(tpl, ids, ctx)
        ok = True
        log.info("SEND ok trigger=%s channel=%s user=%s", tpl.trigger.key, tpl.channel, user.username)
    except Exception as e:  # never break the website because a notification failed
        ok, detail = False, str(e)
        log.error("SEND failed trigger=%s channel=%s user=%s reason=%s", tpl.trigger.key, tpl.channel, user.username, detail)
    NotificationLog.objects.create(trigger_key=tpl.trigger.key, channel=tpl.channel, user=user,
                                   success=ok, detail=detail, is_test=is_test)
    return ok, detail


def fire(trigger_key, user, extra=None):
    """Called by the website when a trigger happens. Sends on every active channel template."""
    results = {}
    log.info("TRIGGER fired key=%s user=%s", trigger_key, user.username)
    for tpl in Template.objects.filter(trigger__key=trigger_key, is_active=True).select_related("trigger"):
        results[tpl.channel] = send_template(tpl, user, extra)
    if not results:
        log.warning("TRIGGER key=%s has no active templates, nothing sent", trigger_key)
    return results


# """Provider integrations + dispatcher."""
# import logging
# import re
# import requests
# from django.conf import settings
# from .models import Template, NotificationLog, PushSubscription

# log = logging.getLogger("notifications")

# TIMEOUT = 20
# VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")


# def build_context(user, extra=None):
#     ctx = {"name": user.first_name or user.username, "username": user.username, "email": user.email}
#     ctx.update(extra or {})
#     return ctx


# def render(text, ctx):
#     return VAR.sub(lambda m: str(ctx.get(m.group(1), "")), text or "")


# def render_wa(text, variables, ctx):
#     """{{1}} -> ctx[variables['1']] ; {{name}} -> ctx['name']"""
#     return VAR.sub(lambda m: str(ctx.get(variables.get(m.group(1), m.group(1)), "")), text or "")


# # ---------------- WhatsApp ----------------
# GRAPH = "https://graph.facebook.com/v25.0"


# # def _wa_headers():
# #     return {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}

# def _wa_headers():
#     return {
#         "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
#         "Content-Type": "application/json",
#     }


# def _clean_phone(phone):
#     if not phone:
#         raise ValueError("User has no phone number")

#     phone = re.sub(r"\D", "", str(phone))

#     if not phone:
#         raise ValueError("Invalid phone number")

#     # India number: 10 digits -> add +91
#     if len(phone) == 10:
#         phone = "91" + phone

#     return phone

# # def send_whatsapp(tpl, phone, ctx):
# #     if not phone:
# #         raise ValueError("User has no phone number")
# #     to = re.sub(r"\D", "", phone)
# #     url = f"{GRAPH}/{settings.PHONE_NUMBER_ID}/messages"
# #     print(url,'url')
# #     if tpl.wa_status == "approved" and tpl.wa_template_name:
# #         params = [{"type": "text", "text": str(ctx.get(v, ""))}
# #                   for _, v in sorted(tpl.variables.items(), key=lambda kv: int(kv[0]))]
# #         print(params,'params')
# #         template = {"name": tpl.wa_template_name, "language": {"code": tpl.wa_language}}
# #         print(template,'template')
# #         if params:
# #             template["components"] = [{"type": "body", "parameters": params}]
# #         payload = {"messaging_product": "whatsapp", "to": to, "type": "template", "template": template}
# #         print(payload,'payload')
# #     else:  # sandbox fallback: free-form text (works inside 24h window for test recipients)
# #         payload = {"messaging_product": "whatsapp", "to": to, "type": "text",
# #                    "text": {"body": render_wa(tpl.body, tpl.variables, ctx)}}
# #         print(payload ,'else payload')
# #     r = requests.post(url, json=payload, headers=_wa_headers(), timeout=TIMEOUT)
# #     print(r,'rrrrrr')
# #     if not r.ok:
# #         raise RuntimeError(f"WhatsApp {r.status_code}: {r.text[:300]}")
# #     return r.text[:200]

# def send_whatsapp(tpl, phone, ctx):
#     """
#     Send WhatsApp notification using Meta WhatsApp Cloud API.
#     """

#     to = _clean_phone(phone)

#     phone_number_id = getattr(settings, "PHONE_NUMBER_ID", "")

#     if not phone_number_id:
#         raise ValueError("PHONE_NUMBER_ID is not configured")

#     if not settings.WHATSAPP_ACCESS_TOKEN:
#         raise ValueError("WHATSAPP_ACCESS_TOKEN is not configured")

#     url = f"{GRAPH}/{phone_number_id}/messages"

#     print("WHATSAPP PHONE NUMBER ID:", phone_number_id)
#     print("WHATSAPP RECIPIENT:", to)
#     print("WHATSAPP URL:", url)

#     # --------------------------------------------------
#     # APPROVED WHATSAPP TEMPLATE
#     # --------------------------------------------------

#     if tpl.wa_status == "approved" and tpl.wa_template_name:

#         parameters = []

#         # variables example:
#         # {"1": "username", "2": "order_id"}

#         for key, variable_name in sorted(
#             tpl.variables.items(),
#             key=lambda item: int(item[0])
#         ):
#             parameters.append(
#                 {
#                     "type": "text",
#                     "text": str(ctx.get(variable_name, "")),
#                 }
#             )

#         template = {
#             "name": tpl.wa_template_name,
#             "language": {
#                 "code": tpl.wa_language or "en_US"
#             },
#         }

#         if parameters:
#             template["components"] = [
#                 {
#                     "type": "body",
#                     "parameters": parameters,
#                 }
#             ]

#         payload = {
#             "messaging_product": "whatsapp",
#             "to": to,
#             "type": "template",
#             "template": template,
#         }
#         print("PAYLOAD:", payload)


#     # --------------------------------------------------
#     # TEST / SANDBOX TEXT MESSAGE
#     # --------------------------------------------------

#     else:

#         body = render_wa(
#             tpl.body,
#             tpl.variables,
#             ctx
#         )

#         payload = {
#             "messaging_product": "whatsapp",
#             "to": to,
#             "type": "text",
#             "text": {
#                 "body": body
#             },
#         }
#         print("PAYLOAD11:", payload)


#     # --------------------------------------------------
#     # SEND REQUEST
#     # --------------------------------------------------

#     try:
#         response = requests.post(
#             url,
#             json=payload,
#             headers=_wa_headers(),
#             timeout=TIMEOUT,
#         )
#     except requests.RequestException as exc:
#         raise RuntimeError(
#             f"WhatsApp request failed: {exc}"
#         )
#     print("STATUS:", response.status_code)
#     print("RESPONSE:", response.text)
#     if not response.ok:
#         try:
#             error_data = response.json()
#         except ValueError:
#             error_data = response.text

#         raise RuntimeError(
#             f"WhatsApp {response.status_code}: {error_data}"
#         )

#     return response.json()

# # def submit_wa_template(tpl):
# #     """Create the template at Meta (if WABA id configured) else auto-approve in sandbox mode."""
# #     if not tpl.wa_template_name:
# #         tpl.wa_template_name = f"{tpl.trigger.key.replace('-', '_')}_{tpl.id}_v1"
# #     if not settings.WHATSAPP_BUSINESS_ACCOUNT_ID:
# #         tpl.wa_status = "approved"
# #         tpl.wa_note = "Sandbox mode: no WABA id set, sending as free-form text."
# #         tpl.save()
# #         return tpl
# #     examples = [ctx for ctx in tpl.variables.values()]
# #     body = {"name": tpl.wa_template_name, "language": tpl.wa_language, "category": "UTILITY",
# #             "components": [{"type": "BODY", "text": tpl.body}]}
# #     if tpl.variables:
# #         body["components"][0]["example"] = {"body_text": [[f"sample_{e}" for e in examples]]}
# #     r = requests.post(f"{GRAPH}/{settings.WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates",
# #                       json=body, headers=_wa_headers(), timeout=TIMEOUT)
# #     if r.ok:
# #         tpl.wa_status = "pending"
# #         tpl.wa_note = "Submitted to Meta. Click Sync until approved."
# #     else:
# #         tpl.wa_status = "rejected"
# #         tpl.wa_note = r.text[:250]
# #     tpl.save()
# #     return tpl

# def submit_wa_template(tpl):
#     """
#     Submit WhatsApp template to Meta.
#     """

#     waba_id = getattr(
#         settings,
#         "WHATSAPP_BUSINESS_ACCOUNT_ID",
#         ""
#     )

#     if not tpl.wa_template_name:
#         tpl.wa_template_name = (
#             f"{tpl.trigger.key.replace('-', '_')}_{tpl.id}_v1"
#         )

#     # Sandbox mode
#     if not waba_id:
#         tpl.wa_status = "approved"
#         tpl.wa_note = (
#             "Sandbox mode. Using test message instead of "
#             "Meta template submission."
#         )
#         tpl.save(
#             update_fields=[
#                 "wa_template_name",
#                 "wa_status",
#                 "wa_note",
#             ]
#         )
#         return tpl

#     body = {
#         "name": tpl.wa_template_name,
#         "language": tpl.wa_language or "en_US",
#         "category": "UTILITY",
#         "components": [
#             {
#                 "type": "BODY",
#                 "text": tpl.body,
#             }
#         ],
#     }

#     # Example values for template variables
#     if tpl.variables:
#         examples = [
#             f"sample_{value}"
#             for _, value in sorted(
#                 tpl.variables.items(),
#                 key=lambda item: int(item[0])
#             )
#         ]

#         body["components"][0]["example"] = {
#             "body_text": [examples]
#         }

#     url = (
#         f"{GRAPH}/{waba_id}/message_templates"
#     )

#     response = requests.post(
#         url,
#         json=body,
#         headers=_wa_headers(),
#         timeout=TIMEOUT,
#     )

#     if response.ok:
#         tpl.wa_status = "pending"
#         tpl.wa_note = (
#             "Submitted to Meta. "
#             "Click Sync until approved."
#         )
#     else:
#         tpl.wa_status = "rejected"
#         tpl.wa_note = response.text[:250]

#     tpl.save()

#     return tpl

# # def sync_wa_template(tpl):
# #     if not settings.WHATSAPP_BUSINESS_ACCOUNT_ID:
# #         return tpl
# #     r = requests.get(f"{GRAPH}/{settings.WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates",
# #                      params={"name": tpl.wa_template_name}, headers=_wa_headers(), timeout=TIMEOUT)
# #     if r.ok and r.json().get("data"):
# #         status = r.json()["data"][0].get("status", "").lower()
# #         tpl.wa_status = status if status in ("approved", "pending", "rejected") else "pending"
# #         tpl.wa_note = f"Meta status: {status}"
# #         tpl.save()
# #     else:
# #         tpl.wa_note = f"Sync failed: {r.text[:200]}"
# #         tpl.save()
# #     return tpl

# def sync_wa_template(tpl):

#     waba_id = getattr(
#         settings,
#         "WHATSAPP_BUSINESS_ACCOUNT_ID",
#         ""
#     )

#     if not waba_id:
#         return tpl

#     url = (
#         f"{GRAPH}/{waba_id}/message_templates"
#     )

#     response = requests.get(
#         url,
#         params={
#             "name": tpl.wa_template_name
#         },
#         headers=_wa_headers(),
#         timeout=TIMEOUT,
#     )

#     if response.ok:

#         data = response.json().get("data", [])

#         if data:

#             status = (
#                 data[0]
#                 .get("status", "")
#                 .lower()
#             )

#             if status in (
#                 "approved",
#                 "pending",
#                 "rejected",
#             ):
#                 tpl.wa_status = status
#             else:
#                 tpl.wa_status = "pending"

#             tpl.wa_note = (
#                 f"Meta status: {status}"
#             )

#         else:
#             tpl.wa_note = (
#                 "Template not found on Meta."
#             )

#     else:
#         tpl.wa_note = (
#             f"Sync failed: {response.text[:200]}"
#         )

#     tpl.save()

#     return tpl

# # ---------------- Email ----------------
# def send_email(tpl, to_email, ctx):
#     if not to_email:
#         raise ValueError("User has no email")
#     subject, html = render(tpl.subject, ctx), render(tpl.body, ctx).replace("\n", "<br>")
#     p = settings.EMAIL_PROVIDER
#     if p == "postmark":
#         r = requests.post("https://api.postmarkapp.com/email", timeout=TIMEOUT,
#                           headers={"X-Postmark-Server-Token": settings.POSTMARKAPP_TOKEN, "Accept": "application/json"},
#                           json={"From": settings.POSTMARK_FROM_EMAIL, "To": to_email, "Subject": subject,
#                                 "HtmlBody": html, "MessageStream": "outbound"})
#     elif p == "brevo":
#         r = requests.post("https://api.brevo.com/v3/smtp/email", timeout=TIMEOUT,
#                           headers={"api-key": settings.BREVO_API_KEY},
#                           json={"sender": {"email": settings.BREVO_FROM_EMAIL}, "to": [{"email": to_email}],
#                                 "subject": subject, "htmlContent": html})
#     elif p == "resend":
#         r = requests.post("https://api.resend.com/emails", timeout=TIMEOUT,
#                           headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
#                           json={"from": settings.RESEND_FROM_EMAIL, "to": [to_email], "subject": subject, "html": html})
#     else:
#         raise ValueError(f"Unknown EMAIL_PROVIDER '{p}'")
#     if not r.ok:
#         raise RuntimeError(f"Email({p}) {r.status_code}: {r.text[:300]}")
#     return r.text[:200]


# # ---------------- Web Push (OneSignal) ----------------
# def send_push(tpl, sub_ids, ctx):
#     if not sub_ids:
#         raise ValueError("User has no push subscription (enable push in the browser first)")
#     r = requests.post("https://api.onesignal.com/notifications?c=push", timeout=TIMEOUT,
#                       headers={"Authorization": f"Key {settings.ONESIGNAL_REST_API_KEY}", "Content-Type": "application/json"},
#                       json={"app_id": settings.ONESIGNAL_APP_ID, "target_channel": "push",
#                             "include_subscription_ids": sub_ids,
#                             "headings": {"en": render(tpl.title, ctx)}, "contents": {"en": render(tpl.body, ctx)}})
#     if not r.ok:
#         raise RuntimeError(f"OneSignal {r.status_code}: {r.text[:300]}")
#     return r.text[:200]


# # ---------------- Dispatcher ----------------
# def send_template(tpl, user, extra=None, is_test=False):
#     ctx = build_context(user, extra)
#     try:
#         if tpl.channel == "whatsapp":
#             phone = getattr(getattr(user, "profile", None), "phone", "")
#             detail = send_whatsapp(tpl, phone, ctx)
#         elif tpl.channel == "email":
#             detail = send_email(tpl, user.email, ctx)
#         else:
#             ids = list(PushSubscription.objects.filter(user=user).values_list("subscription_id", flat=True))
#             detail = send_push(tpl, ids, ctx)
#         ok = True
#     except Exception as e:  # never break the website because a notification failed
#         ok, detail = False, str(e)
#     NotificationLog.objects.create(trigger_key=tpl.trigger.key, channel=tpl.channel, user=user,
#                                    success=ok, detail=detail, is_test=is_test)
#     return ok, detail


# def fire(trigger_key, user, extra=None):
#     """Called by the website when a trigger happens. Sends on every active channel template."""
#     results = {}
#     for tpl in Template.objects.filter(trigger__key=trigger_key, is_active=True).select_related("trigger"):
#         results[tpl.channel] = send_template(tpl, user, extra)
#     return results
