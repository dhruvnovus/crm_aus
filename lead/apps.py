from django.apps import AppConfig


class LeadConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lead'

    def ready(self):
        from . import signals  # noqa: F401
