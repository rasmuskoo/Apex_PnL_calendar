from decimal import Decimal
import re

from django import forms
from django.forms import modelformset_factory

from .models import CopyTradingGroup, Payout, PropAccount, Trade


class TradeFilterForm(forms.Form):
    hot_range = forms.ChoiceField(
        required=False,
        choices=[
            ("today", "Today"),
            ("yesterday", "Yesterday"),
            ("this_week", "This week"),
            ("previous_week", "Previous week"),
            ("this_month", "This month"),
            ("previous_month", "Previous month"),
            ("this_quarter", "This quarter"),
            ("previous_quarter", "Previous quarter"),
            ("this_year", "This year"),
            ("previous_year", "Previous year"),
            ("custom", "Custom date"),
        ],
    )
    month = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    account = forms.ModelChoiceField(required=False, queryset=PropAccount.objects.none())
    stage = forms.ChoiceField(required=False, choices=[("", "All")] + list(PropAccount._meta.get_field("stage").choices))
    evaluation_funded = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All"),
            ("evaluation", "Evaluations"),
            ("funded", "Fundeds"),
        ],
    )

    def __init__(self, *args, account_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = account_qs if account_qs is not None else PropAccount.objects.all()


class TradeForm(forms.ModelForm):
    def __init__(self, *args, account_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = account_qs if account_qs is not None else PropAccount.objects.all()

    class Meta:
        model = Trade
        fields = [
            "trade_date",
            "account",
            "instrument",
            "contracts",
            "contract_type",
            "gross_pnl",
            "broker_fees",
            "notes",
        ]
        widgets = {
            "trade_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class AccountForm(forms.ModelForm):
    ACCOUNT_SIZE_CHOICES = [
        (Decimal("25000"), "25,000"),
        (Decimal("50000"), "50,000"),
        (Decimal("100000"), "100,000"),
        (Decimal("150000"), "150,000"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["external_id"].required = True
        self.fields["external_id"].label = "Account ID (Tradovate/Apex)"
        self.fields["account_size"].widget = forms.Select(
            choices=[(str(value), label) for value, label in self.ACCOUNT_SIZE_CHOICES]
        )

    def clean_external_id(self):
        value = (self.cleaned_data.get("external_id") or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", value):
            raise forms.ValidationError("Use only capital letters A-Z and numbers 0-9 (no spaces, dashes, or symbols).")
        return value

    class Meta:
        model = PropAccount
        fields = [
            "external_id",
            "broker",
            "traildown_type",
            "account_size",
            "evaluation_fee",
            "is_active",
        ]


class PayoutForm(forms.ModelForm):
    def __init__(self, *args, account_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = account_qs if account_qs is not None else PropAccount.objects.all()

    class Meta:
        model = Payout
        fields = ["account", "payout_date", "amount", "notes"]
        widgets = {
            "payout_date": forms.DateInput(attrs={"type": "date"}),
        }


class CopyTradingGroupForm(forms.ModelForm):
    class Meta:
        model = CopyTradingGroup
        fields = ["name"]


class CopyTradingAssignmentForm(forms.ModelForm):
    class Meta:
        model = PropAccount
        fields = ["copy_group", "is_copy_lead"]
        widgets = {
            "is_copy_lead": forms.CheckboxInput(attrs={"class": "lead-star-input"}),
        }


CopyTradingAssignmentFormSet = modelformset_factory(
    PropAccount,
    form=CopyTradingAssignmentForm,
    extra=0,
)


class AccountLifecycleForm(forms.ModelForm):
    class Meta:
        model = PropAccount
        fields = ["stage", "traildown_type", "activation_fee", "is_active"]


AccountLifecycleFormSet = modelformset_factory(
    PropAccount,
    form=AccountLifecycleForm,
    extra=0,
)
