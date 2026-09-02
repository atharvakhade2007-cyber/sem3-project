from django.apps import AppConfig


class StudyCoreConfig(AppConfig):
    name = "study_core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import study_core.signals  # noqa: F401
