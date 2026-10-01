from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("admin/triggers", views.TriggerViewSet)
router.register("admin/templates", views.TemplateViewSet)
router.register("admin/countries", views.CountryViewSet)


urlpatterns = [
    path("countries/", views.countries),
    path("auth/register/", views.register),
    path("auth/login/", views.login),
    path("auth/logout/", views.logout),
    path("auth/me/", views.me),
    path("push/subscribe/", views.push_subscribe),
    path("events/<slug:key>/", views.fire_event),
    path("admin/logs/", views.logs),
    path("", include(router.urls)),
]
