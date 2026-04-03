from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import PropFirm


@receiver(post_migrate)
def seed_default_firms(sender, **kwargs):
    if sender.name != "pnl_calendar":
        return

    defaults = [
        {"name": "Apex Trader Funding", "code": "apex", "funded_account_limit": 20, "display_order": 1, "is_active": True},
    ]

    for payload in defaults:
        PropFirm.objects.update_or_create(code=payload["code"], defaults=payload)

    PropFirm.objects.exclude(code="apex").update(is_active=False)
