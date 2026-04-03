from django.contrib import admin

from .models import CopyTradingGroup, Payout, PropAccount, PropFirm, Trade


@admin.register(PropFirm)
class PropFirmAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "funded_account_limit")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(PropAccount)
class PropAccountAdmin(admin.ModelAdmin):
    list_display = ("nickname", "firm", "stage", "broker", "copy_group", "is_copy_lead", "account_size", "is_active")
    list_filter = ("firm", "stage", "broker", "copy_group", "is_copy_lead", "is_active")
    search_fields = ("nickname", "external_id")


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("trade_date", "account", "contracts", "contract_type", "source_trade", "gross_pnl", "broker_fees", "net_pnl")
    list_filter = ("account__firm", "account__stage", "trade_date")
    search_fields = ("instrument", "notes")


@admin.register(CopyTradingGroup)
class CopyTradingGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("payout_date", "account", "amount")
    list_filter = ("account__firm", "payout_date")
    search_fields = ("account__nickname", "notes")
