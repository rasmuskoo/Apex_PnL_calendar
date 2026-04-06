from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q, Sum


class Stage(models.TextChoices):
    EVALUATION = "evaluation", "Evaluation"
    FUNDED = "funded", "Funded"


class Broker(models.TextChoices):
    TRADOVATE = "tradovate", "Tradovate"
    RITHMIC = "rithmic", "Rithmic"
    OTHER = "other", "Other"


class ContractType(models.TextChoices):
    MINI = "mini", "Mini"
    MICRO = "micro", "Micro"
    OTHER = "other", "Other"


class TraildownType(models.TextChoices):
    INTRADAY = "intraday", "Intraday"
    END_OF_DAY = "end_of_day", "End of day"


class InactiveReason(models.TextChoices):
    NONE = "", "None"
    EVALUATION_BLOWN = "evaluation_blown", "Evaluation blown"
    MAX_PAYOUTS_RECEIVED = "max_payouts_received", "Max payouts received"
    FUNDING_BLOWN = "funding_blown", "Funding blown"


class PropFirm(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    is_active = models.BooleanField(default=True)
    funded_account_limit = models.PositiveIntegerField(default=0)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "name")

    def __str__(self) -> str:
        return self.name


class CopyTradingGroup(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class PropAccount(models.Model):
    firm = models.ForeignKey(PropFirm, on_delete=models.CASCADE, related_name="accounts")
    nickname = models.CharField(max_length=120)
    external_id = models.CharField(max_length=120, blank=True)
    broker = models.CharField(max_length=20, choices=Broker.choices, default=Broker.OTHER)
    traildown_type = models.CharField(max_length=20, choices=TraildownType.choices, default=TraildownType.INTRADAY)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.EVALUATION)
    account_size = models.DecimalField(max_digits=12, decimal_places=2)
    evaluation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    activation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    profit_target_hit_date = models.DateField(null=True, blank=True)
    copy_group = models.ForeignKey(
        CopyTradingGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accounts",
    )
    is_copy_lead = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    inactive_reason = models.CharField(max_length=40, choices=InactiveReason.choices, blank=True, default=InactiveReason.NONE)
    is_hidden_from_accounts = models.BooleanField(default=False)

    class Meta:
        unique_together = ("firm", "nickname")
        ordering = ("firm", "nickname")
        constraints = [
            models.UniqueConstraint(
                fields=["copy_group"],
                condition=Q(is_copy_lead=True),
                name="one_copy_lead_per_group",
            )
        ]

    def __str__(self) -> str:
        return f"{self.firm.name} - {self.nickname}"

    def clean(self) -> None:
        super().clean()
        if self.firm_id and self.firm.code != "apex":
            raise ValidationError({"firm": "This app is configured for Apex Trader Funding only."})

        if self.is_copy_lead and self.copy_group is None:
            raise ValidationError({"is_copy_lead": "Lead account must belong to a copy trading group."})

        if self.copy_group and self.is_copy_lead:
            qs = PropAccount.objects.filter(copy_group=self.copy_group, is_copy_lead=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"is_copy_lead": "Only one lead account is allowed per copy trading group."})

        if self.stage == Stage.FUNDED and self.is_active and self.firm_id and self.firm.funded_account_limit:
            qs = PropAccount.objects.filter(
                firm=self.firm,
                stage=Stage.FUNDED,
                is_active=True,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.count() >= self.firm.funded_account_limit:
                raise ValidationError(
                    {
                        "stage": (
                            f"{self.firm.name} allows up to "
                            f"{self.firm.funded_account_limit} active funded accounts."
                        )
                    }
                )


class Trade(models.Model):
    account = models.ForeignKey(PropAccount, on_delete=models.CASCADE, related_name="trades")
    trade_date = models.DateField()
    instrument = models.CharField(max_length=60, blank=True)
    contracts = models.PositiveIntegerField(default=1)
    contract_type = models.CharField(max_length=20, choices=ContractType.choices, default=ContractType.OTHER)
    gross_pnl = models.DecimalField(max_digits=12, decimal_places=2)
    broker_fees = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    source_trade = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="copied_trades")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-trade_date", "id")

    def __str__(self) -> str:
        return f"{self.trade_date} {self.account} {self.net_pnl}"

    @property
    def net_pnl(self) -> Decimal:
        return self.gross_pnl - self.broker_fees

    @classmethod
    def aggregate_totals(cls, queryset):
        return queryset.aggregate(
            gross_total=Sum("gross_pnl"),
            fees_total=Sum("broker_fees"),
            net_total=Sum(F("gross_pnl") - F("broker_fees")),
        )


class Payout(models.Model):
    account = models.ForeignKey(PropAccount, on_delete=models.CASCADE, related_name="payouts")
    payout_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("payout_date", "id")

    def __str__(self) -> str:
        return f"{self.account} payout {self.amount} on {self.payout_date}"
