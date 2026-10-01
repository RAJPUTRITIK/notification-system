import logging
import time

log = logging.getLogger("requests_log")


class RequestLogMiddleware:
    """One line per API request: method path status duration user ip."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception:
            log.exception("%s %s -> 500 UNHANDLED", request.method, request.path)
            raise
        ms = int((time.monotonic() - start) * 1000)
        if request.path.startswith("/api/"):
            user = getattr(request, "user", None)
            who = user.username if getattr(user, "is_authenticated", False) else "anon"
            ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "-")).split(",")[0]
            level = logging.ERROR if response.status_code >= 500 else logging.WARNING if response.status_code >= 400 else logging.INFO
            log.log(level, "%s %s -> %s %sms user=%s ip=%s", request.method, request.path, response.status_code, ms, who, ip)
        return response
