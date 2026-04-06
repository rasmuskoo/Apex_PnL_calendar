import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import (
    AccountForm,
    AccountLifecycleFormSet,
    CopyTradingAssignmentFormSet,
    CopyTradingGroupForm,
    PayoutForm,
    TradeFilterForm,
    TradeForm,
)
from .models import CopyTradingGroup, DayStatus, InactiveReason, Payout, PropAccount, PropFirm, Stage, Trade, TradingDayStatus
from .rules import (
    APEX_DRAWDOWN_LIMIT,
    APEX_MAX_PAYOUTS,
    APEX_PAYOUT_CAPS_50K,
    APEX_PAYOUT_MIN_DAYS,
    APEX_PAYOUT_MIN_PROFIT,
    evaluate_apex_accounts,
)
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


def _add_months(value: date, months: int) -> date:
    month_index = (value.month - 1) + months
    year = value.year + (month_index // 12)
    month = (month_index % 12) + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _add_years(value: date, years: int) -> date:
    year = value.year + years
    day = value.day
    if value.month == 2 and value.day == 29 and not calendar.isleap(year):
        day = 28
    return date(year, value.month, day)


def _resolve_hot_range_bounds(hot_range: str | None):
    if not hot_range or hot_range == "custom":
        return None, None

    today = date.today()
    if hot_range == "today":
        return today, today
    if hot_range == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if hot_range == "this_week":
        return today - timedelta(days=6), today
    if hot_range == "previous_week":
        end = today - timedelta(days=7)
        return end - timedelta(days=6), end
    if hot_range == "this_month":
        return _add_months(today, -1) + timedelta(days=1), today
    if hot_range == "previous_month":
        this_start = _add_months(today, -1) + timedelta(days=1)
        end = this_start - timedelta(days=1)
        return _add_months(end, -1) + timedelta(days=1), end
    if hot_range == "this_quarter":
        return _add_months(today, -3) + timedelta(days=1), today
    if hot_range == "previous_quarter":
        this_start = _add_months(today, -3) + timedelta(days=1)
        end = this_start - timedelta(days=1)
        return _add_months(end, -3) + timedelta(days=1), end
    if hot_range == "this_year":
        return _add_years(today, -1) + timedelta(days=1), today
    if hot_range == "previous_year":
        this_start = _add_years(today, -1) + timedelta(days=1)
        end = this_start - timedelta(days=1)
        return _add_years(end, -1) + timedelta(days=1), end
    return None, None


def _resolve_date_filters(params):
    hot_range = params.get("hot_range")
    date_from_raw = params.get("date_from")
    date_to_raw = params.get("date_to")
    if not hot_range and not date_from_raw and not date_to_raw:
        hot_range = "this_month"

    hot_from, hot_to = _resolve_hot_range_bounds(hot_range)
    if hot_from and hot_to:
        return hot_from, hot_to

    date_from = None
    date_to = None
    try:
        if date_from_raw:
            date_from = date.fromisoformat(date_from_raw)
    except ValueError:
        date_from = None
    try:
        if date_to_raw:
            date_to = date.fromisoformat(date_to_raw)
    except ValueError:
        date_to = None
    return date_from, date_to


def _scope_from_request(request):
    stage = request.GET.get("evaluation_funded") or request.GET.get("stage")
    return {
        "account_id": request.GET.get("account"),
        "stage": stage,
    }


def _base_filtered_queryset(request):
    qs = Trade.objects.select_related("account", "account__firm").filter(account__firm__code=APEX_FIRM_CODE)
    scope = _scope_from_request(request)

    if scope["account_id"]:
        qs = qs.filter(account_id=scope["account_id"])
    if scope["stage"]:
        qs = qs.filter(account__stage=scope["stage"])

    date_from, date_to = _resolve_date_filters(request.GET)
    if date_from:
        qs = qs.filter(trade_date__gte=date_from)
    if date_to:
        qs = qs.filter(trade_date__lte=date_to)

    return qs


def _rule_scope_accounts(request):
    qs = PropAccount.objects.select_related("firm").filter(
        firm__code=APEX_FIRM_CODE,
        is_active=True,
        is_hidden_from_accounts=False,
    )
    scope = _scope_from_request(request)
    if scope["account_id"]:
        qs = qs.filter(id=scope["account_id"])
    if scope["stage"]:
        qs = qs.filter(stage=scope["stage"])
    return qs


def _build_summary_data(trades, accounts_qs=None):
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
    if accounts_qs is not None:
        fee_totals = accounts_qs.aggregate(
            evaluation_fee_total=Coalesce(Sum("evaluation_fee"), Decimal("0.00")),
            activation_fee_total=Coalesce(Sum("activation_fee"), Decimal("0.00")),
        )
    else:
        fee_totals = {"evaluation_fee_total": Decimal("0.00"), "activation_fee_total": Decimal("0.00")}

    return {
        "net_pnl": totals["net_pnl"],
        "trade_win_pct": (win_count / total_count * 100) if total_count else 0,
        "avg_win_trade": (total_win_amount / win_count) if win_count else 0,
        "avg_loss_trade": (total_loss_amount / loss_count) if loss_count else 0,
        "avg_win_day": (sum(win_days) / len(win_days)) if win_days else 0,
        "avg_loss_day": (sum(loss_days) / len(loss_days)) if loss_days else 0,
        "accounts_used": accounts_used,
        "account_return_pct": account_return_pct,
        "evaluation_fee_total": fee_totals["evaluation_fee_total"],
        "activation_fee_total": fee_totals["activation_fee_total"],
        "streaks": streaks,
    }


def _build_day_nets(trades):
    day_nets = {}
    if hasattr(trades, "order_by"):
        iterable = trades.order_by("trade_date", "id")
    else:
        iterable = sorted(trades, key=lambda trade: (trade.trade_date, getattr(trade, "id", 0)))
    for trade in iterable:
        day_nets.setdefault(trade.trade_date, Decimal("0.00"))
        day_nets[trade.trade_date] += trade.net_pnl
    return day_nets


def _build_dashboard_warnings(accounts, trades, payouts):
    warnings = []
    trades_by_account = {}
    payouts_by_account = {}

    for trade in trades.order_by("trade_date", "id"):
        trades_by_account.setdefault(trade.account_id, []).append(trade)
    for payout in payouts.order_by("payout_date", "id"):
        payouts_by_account.setdefault(payout.account_id, []).append(payout)

    for account in accounts:
        account_trades = trades_by_account.get(account.id, [])
        day_nets = _build_day_nets(account_trades)

        running_equity = account.account_size
        peak_equity = account.account_size
        worst_drawdown = Decimal("0.00")
        for day in sorted(day_nets.keys()):
            running_equity += day_nets[day]
            if running_equity > peak_equity:
                peak_equity = running_equity
            drawdown = peak_equity - running_equity
            if drawdown > worst_drawdown:
                worst_drawdown = drawdown

        drawdown_buffer = APEX_DRAWDOWN_LIMIT - worst_drawdown
        if drawdown_buffer < Decimal("1000.00"):
            warnings.append(
                {
                    "type": "drawdown",
                    "account": account,
                    "detail": f"Drawdown buffer ${drawdown_buffer:.2f} (worst ${worst_drawdown:.2f} / limit ${APEX_DRAWDOWN_LIMIT:.2f})",
                }
            )

        if account.stage != Stage.FUNDED:
            continue

        account_payouts = payouts_by_account.get(account.id, [])
        payout_count = len(account_payouts)
        if payout_count >= APEX_MAX_PAYOUTS:
            warnings.append(
                {
                    "type": "max_payout",
                    "account": account,
                    "detail": f"Max payout status reached ({payout_count}/{APEX_MAX_PAYOUTS}).",
                }
            )
            continue

        last_payout_date = account_payouts[-1].payout_date if account_payouts else None
        payout_window_day_nets = {
            day: amount for day, amount in day_nets.items() if last_payout_date is None or day > last_payout_date
        }
        payout_window_days = len(payout_window_day_nets)
        payout_window_net = sum(payout_window_day_nets.values(), Decimal("0.00"))
        eligible = payout_window_days >= APEX_PAYOUT_MIN_DAYS and payout_window_net >= APEX_PAYOUT_MIN_PROFIT
        if eligible:
            next_cap = APEX_PAYOUT_CAPS_50K[payout_count] if payout_count < len(APEX_PAYOUT_CAPS_50K) else Decimal("0.00")
            accessible = min(next_cap, payout_window_net) if next_cap > 0 else payout_window_net
            warnings.append(
                {
                    "type": "payout_eligible",
                    "account": account,
                    "detail": f"Eligible payout ${accessible:.2f} (cap ${next_cap:.2f}, window net ${payout_window_net:.2f}).",
                }
            )

    return warnings


def dashboard(request):
    month_start = _parse_month(request.GET.get("month"))
    month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])

    accounts_qs = PropAccount.objects.select_related("firm").filter(
        firm__code=APEX_FIRM_CODE,
        is_active=True,
        is_hidden_from_accounts=False,
    ).order_by("nickname")

    trades = _base_filtered_queryset(request)

    form_data = request.GET.copy()
    if not form_data.get("hot_range") and not form_data.get("date_from") and not form_data.get("date_to"):
        form_data["hot_range"] = "this_month"
    hot_from, hot_to = _resolve_date_filters(form_data)
    if hot_from:
        form_data["date_from"] = hot_from.isoformat()
    if hot_to:
        form_data["date_to"] = hot_to.isoformat()

    form = TradeFilterForm(
        form_data or None,
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
    day_status_map = {
        row.trade_date: row.status
        for row in TradingDayStatus.objects.filter(
            firm__code=APEX_FIRM_CODE,
            trade_date__gte=month_grid[0][0] if month_grid else month_start,
            trade_date__lte=month_grid[-1][-1] if month_grid else month_end,
        )
    }
    scoped_accounts_qs = _rule_scope_accounts(request)
    scoped_accounts = list(scoped_accounts_qs)
    summary = _build_summary_data(trades, accounts_qs=scoped_accounts_qs)
    scoped_trades = Trade.objects.filter(account__in=scoped_accounts).select_related("account", "account__firm")
    scoped_payouts = Payout.objects.filter(account__in=scoped_accounts).select_related("account", "account__firm")
    apex_accounts = [account for account in scoped_accounts if account.firm.code == "apex"]
    warning_items = _build_dashboard_warnings(
        apex_accounts,
        scoped_trades.filter(account__in=apex_accounts),
        scoped_payouts.filter(account__in=apex_accounts),
    )

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
        "day_status_map": day_status_map,
        "summary": summary,
        "warning_items": warning_items,
        "prev_query": prev_params.urlencode(),
        "next_query": next_params.urlencode(),
    }

    if request.headers.get("HX-Request"):
        return render(request, "pnl_calendar/_calendar_block.html", context)
    return render(request, "pnl_calendar/dashboard.html", context)


def add_trade(request):
    if request.method != "POST":
        return redirect("pnl_calendar:dashboard")

    apex_accounts = PropAccount.objects.filter(
        firm__code=APEX_FIRM_CODE,
        is_active=True,
        is_hidden_from_accounts=False,
    ).order_by("nickname")
    form = TradeForm(request.POST, account_qs=apex_accounts)
    if form.is_valid():
        trade = form.save()
        TradingDayStatus.objects.filter(
            firm__code=APEX_FIRM_CODE,
            trade_date=trade.trade_date,
        ).delete()
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


def set_day_status(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    trade_date_raw = request.POST.get("trade_date")
    status = request.POST.get("status")
    if status not in {DayStatus.NO_TRADE, DayStatus.MARKET_CLOSED}:
        messages.error(request, "Invalid day status.")
        return redirect(request.META.get("HTTP_REFERER", reverse("pnl_calendar:dashboard")))

    try:
        parsed_date = date.fromisoformat(trade_date_raw or "")
    except ValueError:
        messages.error(request, "Invalid date.")
        return redirect(request.META.get("HTTP_REFERER", reverse("pnl_calendar:dashboard")))

    firm = PropFirm.objects.filter(code=APEX_FIRM_CODE).first()
    if not firm:
        messages.error(request, "Apex firm is not configured.")
        return redirect(request.META.get("HTTP_REFERER", reverse("pnl_calendar:dashboard")))

    TradingDayStatus.objects.update_or_create(
        firm=firm,
        trade_date=parsed_date,
        defaults={"status": status},
    )
    messages.success(request, f"{parsed_date} marked as {DayStatus(status).label.lower()}.")
    return redirect(request.META.get("HTTP_REFERER", reverse("pnl_calendar:dashboard")))


def settings_view(request):
    apex_firm, _ = PropFirm.objects.get_or_create(
        code=APEX_FIRM_CODE,
        defaults={"name": "Apex Trader Funding", "funded_account_limit": 20, "display_order": 1, "is_active": True},
    )
    account_queryset = PropAccount.objects.select_related("firm", "copy_group").filter(firm__code=APEX_FIRM_CODE).order_by("nickname")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_payout":
            payout_form = PayoutForm(request.POST, account_qs=account_queryset, prefix="payout")
            if payout_form.is_valid():
                payout_form.save()
                messages.success(request, "Payout recorded.")
            else:
                messages.error(request, f"Could not record payout: {payout_form.errors.as_text()}")
        elif action == "save_group":
            group_form = CopyTradingGroupForm(request.POST, prefix="copy_group")
            if group_form.is_valid() and group_form.cleaned_data.get("name"):
                group_form.save()
                messages.success(request, "Copy trading group created.")
            else:
                messages.error(request, f"Could not create group: {group_form.errors.as_text()}")
        elif action == "save_assignments":
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
                    for err in assignment_errors:
                        messages.error(request, err)
                else:
                    assignment_formset.save()
                    messages.success(request, "Copy trading setup saved.")
            else:
                messages.error(request, f"Could not save copy trading setup: {assignment_formset.errors}")
        elif action == "save_account_lifecycle":
            lifecycle_formset = AccountLifecycleFormSet(request.POST, queryset=account_queryset, prefix="account_lifecycle")
            if lifecycle_formset.is_valid():
                lifecycle_formset.save()
                messages.success(request, "Account stages and activation fees updated.")
            else:
                messages.error(request, f"Could not update account lifecycle: {lifecycle_formset.errors}")
        else:
            messages.error(request, "Unknown settings action.")
        return redirect(request.META.get("HTTP_REFERER", reverse("pnl_calendar:dashboard")))

    payout_form = PayoutForm(account_qs=account_queryset, prefix="payout")
    group_form = CopyTradingGroupForm(prefix="copy_group")
    assignment_formset = CopyTradingAssignmentFormSet(queryset=account_queryset, prefix="copy_assign")
    lifecycle_formset = AccountLifecycleFormSet(queryset=account_queryset, prefix="account_lifecycle")

    context = {
        "payout_form": payout_form,
        "group_form": group_form,
        "assignment_formset": assignment_formset,
        "lifecycle_formset": lifecycle_formset,
        "copy_groups": CopyTradingGroup.objects.order_by("name"),
        "accounts": account_queryset,
        "payouts": Payout.objects.select_related("account", "account__firm").order_by("-payout_date", "-id"),
    }

    if request.headers.get("HX-Request"):
        return render(request, "pnl_calendar/_settings_modal_content.html", context)
    return render(request, "pnl_calendar/settings.html", context)


def accounts_view(request):
    apex_firm, _ = PropFirm.objects.get_or_create(
        code=APEX_FIRM_CODE,
        defaults={"name": "Apex Trader Funding", "funded_account_limit": 20, "display_order": 1, "is_active": True},
    )
    accounts_qs = PropAccount.objects.select_related("firm", "copy_group").filter(firm__code=APEX_FIRM_CODE).order_by("nickname")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_account":
            account_form = AccountForm(request.POST, prefix="account")
            account_form.instance.firm = apex_firm
            if account_form.is_valid():
                account = account_form.save(commit=False)
                account.firm = apex_firm
                account.nickname = account.external_id
                account.stage = Stage.EVALUATION
                account.is_active = True
                account.inactive_reason = InactiveReason.NONE
                account.is_hidden_from_accounts = False
                duplicate_exists = PropAccount.objects.filter(firm=apex_firm, nickname=account.nickname).exists()
                if duplicate_exists:
                    messages.error(request, "An account with this Account ID already exists.")
                else:
                    account.save()
                    messages.success(request, "Account added.")
            else:
                messages.error(request, f"Could not add account: {account_form.errors.as_text()}")
        elif action == "account_row_action":
            account_id = request.POST.get("account_id")
            row_action = request.POST.get("row_action")
            account = accounts_qs.filter(id=account_id).first()
            if not account:
                messages.error(request, "Account not found.")
            else:
                if row_action == "move_to_funded":
                    account.stage = Stage.FUNDED
                    account.is_active = True
                    account.inactive_reason = InactiveReason.NONE
                    account.is_hidden_from_accounts = False
                    account.save(update_fields=["stage", "is_active", "inactive_reason", "is_hidden_from_accounts"])
                    messages.success(request, f"{account.external_id or account.nickname} moved to Funded.")
                elif row_action == "evaluation_blown":
                    account.is_active = False
                    account.inactive_reason = InactiveReason.EVALUATION_BLOWN
                    account.is_hidden_from_accounts = False
                    account.save(update_fields=["is_active", "inactive_reason", "is_hidden_from_accounts"])
                    messages.success(request, f"{account.external_id or account.nickname} marked as Evaluation blown.")
                elif row_action == "max_payouts_received":
                    account.is_active = False
                    account.inactive_reason = InactiveReason.MAX_PAYOUTS_RECEIVED
                    account.is_hidden_from_accounts = False
                    account.save(update_fields=["is_active", "inactive_reason", "is_hidden_from_accounts"])
                    messages.success(request, f"{account.external_id or account.nickname} marked as Max payouts received.")
                elif row_action == "funding_blown":
                    account.is_active = False
                    account.inactive_reason = InactiveReason.FUNDING_BLOWN
                    account.is_hidden_from_accounts = False
                    account.save(update_fields=["is_active", "inactive_reason", "is_hidden_from_accounts"])
                    messages.success(request, f"{account.external_id or account.nickname} marked as Funding blown.")
                elif row_action == "reactivate":
                    account.is_active = True
                    account.inactive_reason = InactiveReason.NONE
                    account.is_hidden_from_accounts = False
                    account.save(update_fields=["is_active", "inactive_reason", "is_hidden_from_accounts"])
                    messages.success(request, f"{account.external_id or account.nickname} reactivated.")
                else:
                    messages.error(request, "Unknown account action.")
        elif action == "clear_inactive_eval":
            updated = accounts_qs.filter(stage=Stage.EVALUATION, is_active=False, is_hidden_from_accounts=False).update(
                is_hidden_from_accounts=True
            )
            messages.success(request, f"Cleared {updated} inactive evaluation account(s) from the list.")
        elif action == "clear_inactive_funded":
            updated = accounts_qs.filter(stage=Stage.FUNDED, is_active=False, is_hidden_from_accounts=False).update(
                is_hidden_from_accounts=True
            )
            messages.success(request, f"Cleared {updated} inactive funded account(s) from the list.")
        return redirect("pnl_calendar:accounts")

    account_form = AccountForm(prefix="account")
    active_eval_accounts = accounts_qs.filter(stage=Stage.EVALUATION, is_active=True, is_hidden_from_accounts=False)
    active_funded_accounts = accounts_qs.filter(stage=Stage.FUNDED, is_active=True, is_hidden_from_accounts=False)
    inactive_eval_accounts = accounts_qs.filter(stage=Stage.EVALUATION, is_active=False, is_hidden_from_accounts=False)
    inactive_funded_accounts = accounts_qs.filter(stage=Stage.FUNDED, is_active=False, is_hidden_from_accounts=False)

    return render(
        request,
        "pnl_calendar/accounts.html",
        {
            "account_form": account_form,
            "active_eval_accounts": active_eval_accounts,
            "active_funded_accounts": active_funded_accounts,
            "inactive_eval_accounts": inactive_eval_accounts,
            "inactive_funded_accounts": inactive_funded_accounts,
        },
    )


def rule_monitor_view(request):
    scoped_accounts_qs = _rule_scope_accounts(request)
    scoped_accounts = list(scoped_accounts_qs)
    scoped_trades = Trade.objects.filter(account__in=scoped_accounts).select_related("account", "account__firm")
    scoped_payouts = Payout.objects.filter(account__in=scoped_accounts).select_related("account", "account__firm")
    apex_accounts = [account for account in scoped_accounts if account.firm.code == "apex"]
    apex_reports = evaluate_apex_accounts(
        accounts=apex_accounts,
        trades=scoped_trades.filter(account__in=apex_accounts),
        payouts=scoped_payouts.filter(account__in=apex_accounts),
        today=date.today(),
    ) if apex_accounts else []
    return render(request, "pnl_calendar/rule_monitor.html", {"apex_reports": apex_reports})
