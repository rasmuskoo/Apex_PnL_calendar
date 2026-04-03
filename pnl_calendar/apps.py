from django.apps import AppConfig


class PnlCalendarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pnl_calendar"

    def ready(self) -> None:
        from . import signals  # noqa: F401
