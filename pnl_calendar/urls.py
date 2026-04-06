from django.urls import path

from . import views

app_name = "pnl_calendar"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("accounts/", views.accounts_view, name="accounts"),
    path("rule-monitor/", views.rule_monitor_view, name="rule_monitor"),
    path("trade/add/", views.add_trade, name="add_trade"),
    path("settings/", views.settings_view, name="settings"),
]
