from django import forms
from django.forms import modelformset_factory

from .models import CopyTradingGroup, Payout, PropAccount, Trade


class TradeFilterForm(forms.Form):
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
    class Meta:
        model = PropAccount
        fields = [
            "nickname",
            "external_id",
            "broker",
            "stage",
            "account_size",
            "activation_fee",
            "profit_target_hit_date",
            "is_active",
        ]
        widgets = {
            "profit_target_hit_date": forms.DateInput(attrs={"type": "date"}),
        }


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
