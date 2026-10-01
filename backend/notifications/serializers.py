from rest_framework import serializers
from .models import Trigger, Template, NotificationLog, Country


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = "__all__"
        read_only_fields = ["wa_status", "wa_note", "wa_template_name"]


class TriggerSerializer(serializers.ModelSerializer):
    templates = TemplateSerializer(many=True, read_only=True)

    class Meta:
        model = Trigger
        fields = ["id", "key", "name", "description", "templates"]


class LogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = NotificationLog
        fields = "__all__"

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "name", "iso_code", "dial_code", "is_active"]
