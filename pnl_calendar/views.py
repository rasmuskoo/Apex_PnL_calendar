import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import (
    AccountForm,
    CopyTradingAssignmentFormSet,
    CopyTradingGroupForm,
    PayoutForm,
    TradeFilterForm,
    TradeForm,
)
from .models import CopyTradingGroup, Payout, PropAccount, PropFirm, Trade
from .rules import evaluate_apex_accounts
from .services import build_month_grid, day_and_trade_streaks

APEX_FIRM_CODE = "apex"


def _parse_month(month_raw: str | None) -> date:
    if not month_raw:
        today = date.today()
        return today.replace(day=1)
    try:
        parsed = datetime.strptime(month_raw, "%Y-%m-%d").date()
        return parsed.replace(day=1)
    except ValueError:
        today = date.today()
        return today.replace(day=1)


def _scope_from_request(request):
    return {
        "account_id": request.GET.get("account"),
        "stage": request.GET.get("stage"),
    }


def _base_filtered_queryset(request):
    qs = Trade.objects.select_related("account", "account__firm").filter(account__firm__code=APEX_FIRM_CODE)
    scope = _scope_from_request(request)

    if scope["account_id"]:
        qs = qs.filter(account_id=scope["account_id"])
    if scope["stage"]:
        qs = qs.filter(account__stage=scope["stage"])

    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if date_from:
        qs = qs.filter(trade_date__gte=date_from)
    if date_to:
        qs = qs.filter(trade_date__lte=date_to)

    return qs


def _rule_scope_accounts(request):
    qs = PropAccount.objects.select_related("firm").filter(firm__code=APEX_FIRM_CODE)
    scope = _scope_from_request(request)
    if scope["account_id"]:
        qs = qs.filter(id=scope["account_id"])
    if scope["stage"]:
        qs = qs.filter(stage=scope["stage"])
    return qs


def _build_summary_data(trades):
    net_expr = F("gross_pnl") - F("broker_fees")
    totals = trades.aggregate(
        net_pnl=Coalesce(Sum(net_expr), Decimal("0.00")),
        fees=Coalesce(Sum("broker_fees"), Decimal("0.00")),
    )

    wins_qs = trades.annotate(net=net_expr).filter(net__gt=0)
    losses_qs = trades.annotate(net=net_expr).filter(net__lt=0)
    win_count = wins_qs.count()
    loss_count = losses_qs.count()
    total_count = trades.count()

    daily_rows = (
        trades.values("trade_date")
        .annotate(net=Coalesce(Sum(net_expr), Decimal("0.00")))
        .order_by("trade_date")
    )
    day_nets = [row["net"] for row in daily_rows]
    win_days = [v for v in day_nets if v > 0]
    loss_days = [v for v in day_nets if v < 0]

    total_win_amount = wins_qs.aggregate(v=Coalesce(Sum(net_expr), Decimal("0.00")))["v"]
    total_loss_amount = losses_qs.aggregate(v=Coalesce(Sum(net_expr), Decimal("0.00")))["v"]

    streaks = day_and_trade_streaks(trades)
    accounts_used = trades.values("account").distinct().count()
    total_account_size = (
        trades.values("account")
        .distinct()
        .aggregate(total=Coalesce(Sum("account__account_size"), Decimal("0.00")))["total"]
    )
    account_return_pct = (
        (totals["net_pnl"] / total_account_size) * Decimal("100")
        if total_account_size
        else Decimal("0.00")
    )

    return {
        "net_pnl": totals["net_pnl"],
        "trade_win_pct": (win_count / total_count * 100) if total_count else 0,
        "avg_win_trade": (total_win_amount / win_count) if win_count else 0,
        "avg_loss_trade": (total_loss_amount / loss_count) if loss_count else 0,
        "avg_win_day": (sum(win_days) / len(win_days)) if win_days else 0,
        "avg_loss_day": (sum(loss_days) / len(loss_days)) if loss_days else 0,
        "accounts_used": accounts_used,
        "account_return_pct": account_return_pct,
        "streaks": streaks,
    }


def dashboard(request):
    month_start = _parse_month(request.GET.get("month"))
    month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])

    accounts_qs = PropAccount.objects.select_related("firm").filter(firm__code=APEX_FIRM_CODE).order_by("nickname")

    trades = _base_filtered_queryset(request)

    form = TradeFilterForm(
        request.GET or None,
        account_qs=accounts_qs,
        initial={"month": month_start},
    )

    if form.is_valid():
        cleaned = form.cleaned_data
        if cleaned.get("month"):
            month_start = cleaned["month"].replace(day=1)
            month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])

    month_trades = trades.filter(trade_date__gte=month_start, trade_date__lte=month_end)

    daily = (
        month_trades.values("trade_date")
        .annotate(
            trades_count=Count("id"),
            net=Coalesce(Sum(F("gross_pnl") - F("broker_fees")), Decimal("0.00")),
        )
        .order_by("trade_date")
    )
    day_map = {row["trade_date"]: row for row in daily}

    month_grid = build_month_grid(month_start.year, month_start.month)
    summary = _build_summary_data(trades)
    scoped_accounts = list(_rule_scope_accounts(request))
    scoped_trades = Trade.objects.filter(account__in=scoped_accounts).select_related("account", "account__firm")
    scoped_payouts = Payout.objects.filter(account__in=scoped_accounts).select_related("account", "account__firm")
    apex_accounts = [account for account in scoped_accounts if account.firm.code == "apex"]
    apex_reports = evaluate_apex_accounts(
        accounts=apex_accounts,
        trades=scoped_trades.filter(account__in=apex_accounts),
        payouts=scoped_payouts.filter(account__in=apex_accounts),
        today=date.today(),
    ) if apex_accounts else []

    params = request.GET.copy()
    prev_month = (month_start - timedelta(days=1)).replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    prev_params = params.copy()
    prev_params["month"] = prev_month.isoformat()
    next_params = params.copy()
    next_params["month"] = next_month.isoformat()

    context = {
        "filter_form": form,
        "trade_form": TradeForm(account_qs=accounts_qs),
        "month_start": month_start,
        "month_grid": month_grid,
        "day_map": day_map,
        "summary": summary,
        "apex_reports": apex_reports,
        "prev_query": prev_params.urlencode(),
        "next_query": next_params.urlencode(),
    }

    if request.headers.get("HX-Request"):
        return render(request, "pnl_calendar/_calendar_block.html", context)
    return render(request, "pnl_calendar/dashboard.html", context)


def add_trade(request):
    if request.method != "POST":
        return redirect("pnl_calendar:dashboard")

    apex_accounts = PropAccount.objects.filter(firm__code=APEX_FIRM_CODE, is_active=True).order_by("nickname")
    form = TradeForm(request.POST, account_qs=apex_accounts)
    if form.is_valid():
        trade = form.save()
        copied_count = 0
        lead_account = trade.account
        if lead_account.copy_group_id and lead_account.is_copy_lead and trade.source_trade_id is None:
            followers = PropAccount.objects.filter(
                copy_group_id=lead_account.copy_group_id,
                is_active=True,
            ).exclude(pk=lead_account.pk)
            for follower in followers:
                Trade.objects.create(
                    account=follower,
                    trade_date=trade.trade_date,
                    instrument=trade.instrument,
                    contracts=trade.contracts,
                    contract_type=trade.contract_type,
                    gross_pnl=trade.gross_pnl,
                    broker_fees=trade.broker_fees,
                    source_trade=trade,
                    notes=f"Copied from lead {lead_account.nickname}. {trade.notes}".strip(),
                )
                copied_count += 1

        if copied_count:
            messages.success(request, f"Trade saved and copied to {copied_count} account(s).")
        else:
            messages.success(request, "Trade saved.")
    else:
        messages.error(request, f"Could not save trade: {form.errors.as_text()}")
    return redirect(request.META.get("HTTP_REFERER", reverse("pnl_calendar:dashboard")))


def settings_view(request):
    apex_firm, _ = PropFirm.objects.get_or_create(
        code=APEX_FIRM_CODE,
        defaults={"name": "Apex Trader Funding", "funded_account_limit": 20, "display_order": 1, "is_active": True},
    )
    account_queryset = PropAccount.objects.select_related("firm", "copy_group").filter(firm__code=APEX_FIRM_CODE).order_by("nickname")
    if request.method == "POST":
        updated_anything = False
        had_errors = False
        account_form = AccountForm(request.POST, prefix="account")
        if account_form.is_valid() and account_form.cleaned_data.get("nickname"):
            account = account_form.save(commit=False)
            account.firm = apex_firm
            account.save()
            updated_anything = True

        payout_form = PayoutForm(request.POST, account_qs=account_queryset, prefix="payout")
        if payout_form.is_valid() and payout_form.cleaned_data.get("account") and payout_form.cleaned_data.get("amount"):
            payout_form.save()
            updated_anything = True

        group_form = CopyTradingGroupForm(request.POST, prefix="copy_group")
        if group_form.is_valid() and group_form.cleaned_data.get("name"):
            group_form.save()
            updated_anything = True

        assignment_formset = CopyTradingAssignmentFormSet(request.POST, queryset=account_queryset, prefix="copy_assign")
        if assignment_formset.is_valid():
            lead_per_group = {}
            assignment_errors = []
            for form_row in assignment_formset.forms:
                group = form_row.cleaned_data.get("copy_group")
                is_lead = form_row.cleaned_data.get("is_copy_lead")
                account = form_row.instance
                if is_lead and not group:
                    assignment_errors.append(f"{account.nickname}: lead account requires a trading group.")
                if group and is_lead:
                    lead_per_group.setdefault(group.id, 0)
                    lead_per_group[group.id] += 1

            duplicate_leads = [group_id for group_id, count in lead_per_group.items() if count > 1]
            if duplicate_leads:
                assignment_errors.append("Only one lead account is allowed per copy trading group.")

            if assignment_errors:
                had_errors = True
                for err in assignment_errors:
                    messages.error(request, err)
            else:
                assignment_formset.save()
                updated_anything = True

        if not had_errors:
            messages.success(request, "Settings updated." if updated_anything else "No settings changes detected.")
        return redirect("pnl_calendar:settings")

    account_form = AccountForm(prefix="account")
    payout_form = PayoutForm(account_qs=account_queryset, prefix="payout")
    group_form = CopyTradingGroupForm(prefix="copy_group")
    assignment_formset = CopyTradingAssignmentFormSet(queryset=account_queryset, prefix="copy_assign")

    return render(
        request,
        "pnl_calendar/settings.html",
        {
            "account_form": account_form,
            "payout_form": payout_form,
            "group_form": group_form,
            "assignment_formset": assignment_formset,
            "copy_groups": CopyTradingGroup.objects.order_by("name"),
            "accounts": account_queryset,
            "payouts": Payout.objects.select_related("account", "account__firm").order_by("-payout_date", "-id"),
        },
    )
