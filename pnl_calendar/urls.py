from django.urls import path

from . import views

app_name = "pnl_calendar"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("trade/add/", views.add_trade, name="add_trade"),
    path("settings/", views.settings_view, name="settings"),
]
