from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from .models import Broker, ContractType, Stage

APEX_50K_PROFIT_TARGET = Decimal("3000.00")
APEX_DRAWDOWN_LIMIT = Decimal("2000.00")
APEX_DAILY_LOSS_LIMIT = Decimal("1000.00")
APEX_ACTIVATION_FEE = Decimal("109.00")
APEX_ACTIVATION_WINDOW_DAYS = 7
APEX_PAYOUT_MIN_DAYS = 5
APEX_PAYOUT_MIN_PROFIT = Decimal("250.00")
APEX_MAX_PAYOUTS = 6
APEX_PAYOUT_CAPS_50K = [
    Decimal("1500.00"),
    Decimal("1500.00"),
    Decimal("2000.00"),
    Decimal("2500.00"),
    Decimal("2500.00"),
    Decimal("3000.00"),
]


def evaluate_apex_accounts(accounts, trades, payouts, today):
    trades_by_account = defaultdict(list)
    for trade in trades.order_by("trade_date", "id"):
        trades_by_account[trade.account_id].append(trade)

    payouts_by_account = defaultdict(list)
    for payout in payouts.order_by("payout_date", "id"):
        payouts_by_account[payout.account_id].append(payout)

    funded_active_count = sum(
        1
        for account in accounts
        if account.stage == Stage.FUNDED and account.is_active
    )

    reports = []
    for account in accounts:
        account_trades = trades_by_account.get(account.id, [])
        account_payouts = payouts_by_account.get(account.id, [])
        reports.append(
            _evaluate_apex_account(
                account=account,
                trades=account_trades,
                payouts=account_payouts,
                today=today,
                funded_active_count=funded_active_count,
            )
        )

    return reports


def _evaluate_apex_account(account, trades, payouts, today, funded_active_count):
    checks = []
    day_nets = _build_day_nets(trades)

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

    drawdown_ok = worst_drawdown <= APEX_DRAWDOWN_LIMIT
    checks.append(
        _check(
            "EOD Drawdown",
            drawdown_ok,
            f"Worst drawdown ${worst_drawdown:.2f} / limit ${APEX_DRAWDOWN_LIMIT:.2f}",
            "breach" if not drawdown_ok else "ok",
        )
    )

    worst_day = min(day_nets.values()) if day_nets else Decimal("0.00")
    daily_ok = worst_day >= -APEX_DAILY_LOSS_LIMIT
    if worst_day < -APEX_DAILY_LOSS_LIMIT:
        daily_level = "breach"
    elif worst_day == -APEX_DAILY_LOSS_LIMIT:
        daily_level = "warn"
    else:
        daily_level = "ok"
    checks.append(
        _check(
            "Daily Loss Limit",
            daily_ok,
            f"Worst day ${worst_day:.2f} / limit -${APEX_DAILY_LOSS_LIMIT:.2f}",
            daily_level,
        )
    )

    net_pnl = sum((t.net_pnl for t in trades), Decimal("0.00"))
    trading_days = len(day_nets)

    if account.stage == Stage.EVALUATION:
        checks.extend(_evaluation_checks(account, net_pnl, trading_days, today))
    else:
        checks.extend(_funded_checks(account, trades, payouts, day_nets, net_pnl, trading_days, funded_active_count))

    breach_count = sum(1 for check in checks if check["level"] == "breach")
    warn_count = sum(1 for check in checks if check["level"] == "warn")

    return {
        "account": account,
        "checks": checks,
        "net_pnl": net_pnl,
        "trading_days": trading_days,
        "breach_count": breach_count,
        "warn_count": warn_count,
    }


def _evaluation_checks(account, net_pnl, trading_days, today):
    checks = []
    min_days_ok = trading_days >= 1
    checks.append(_check("Min Days to Pass", min_days_ok, f"{trading_days} trading day(s), need 1", "breach" if not min_days_ok else "ok"))

    profit_target = _profit_target_for_account(account.account_size)
    target_ok = net_pnl >= profit_target if profit_target > 0 else False
    target_level = "ok" if target_ok else "warn"
    target_detail = (
        f"Net ${net_pnl:.2f} / target ${profit_target:.2f}"
        if profit_target > 0
        else f"No Apex profit target configured for account size {account.account_size:.2f}"
    )
    checks.append(
        _check(
            "Profit Target",
            target_ok,
            target_detail,
            target_level,
        )
    )

    broker_ok = account.broker == Broker.TRADOVATE
    checks.append(
        _check(
            "Broker",
            broker_ok,
            f"Configured broker: {account.get_broker_display()}",
            "warn" if not broker_ok else "ok",
        )
    )

    fee_ok = account.activation_fee == APEX_ACTIVATION_FEE
    checks.append(
        _check(
            "Activation Fee",
            fee_ok,
            f"Configured ${account.activation_fee:.2f} / expected ${APEX_ACTIVATION_FEE:.2f}",
            "warn" if not fee_ok else "ok",
        )
    )

    if account.profit_target_hit_date:
        deadline = account.profit_target_hit_date + timedelta(days=APEX_ACTIVATION_WINDOW_DAYS)
        deadline_ok = today <= deadline
        checks.append(
            _check(
                "Activation Deadline",
                deadline_ok,
                f"Target hit {account.profit_target_hit_date}, deadline {deadline}",
                "breach" if not deadline_ok else "ok",
            )
        )
    elif target_ok:
        checks.append(
            _check(
                "Activation Deadline",
                False,
                "Profit target is reached but hit-date is missing in account settings",
                "warn",
            )
        )
    else:
        checks.append(
            _check(
                "Activation Deadline",
                True,
                "Not applicable until profit target is reached",
                "ok",
            )
        )

    return checks


def _funded_checks(account, trades, payouts, day_nets, net_pnl, trading_days, funded_active_count):
    checks = []

    max_accounts_ok = funded_active_count <= 20
    checks.append(
        _check(
            "Max Funded Accounts",
            max_accounts_ok,
            f"Active funded accounts: {funded_active_count} / 20",
            "breach" if not max_accounts_ok else "ok",
        )
    )

    mini_ok = all(
        (trade.contract_type != ContractType.MINI) or (trade.contracts <= 4)
        for trade in trades
    )
    micro_ok = all(
        (trade.contract_type != ContractType.MICRO) or (trade.contracts <= 40)
        for trade in trades
    )
    contract_ok = mini_ok and micro_ok
    checks.append(
        _check(
            "Contract Size",
            contract_ok,
            "Limits: mini <= 4, micro <= 40",
            "breach" if not contract_ok else "ok",
        )
    )

    positive_days = [amount for amount in day_nets.values() if amount > 0]
    total_positive = sum(positive_days, Decimal("0.00"))
    largest_positive = max(positive_days) if positive_days else Decimal("0.00")
    consistency_ratio = (largest_positive / total_positive * Decimal("100")) if total_positive > 0 else Decimal("0.00")
    consistency_ok = consistency_ratio <= Decimal("50.00") if total_positive > 0 else True
    checks.append(
        _check(
            "Consistency 50%",
            consistency_ok,
            f"Largest positive day is {consistency_ratio:.2f}% of positive PnL",
            "warn" if not consistency_ok else "ok",
        )
    )

    payout_count = len(payouts)
    payouts_ok = payout_count <= APEX_MAX_PAYOUTS
    checks.append(
        _check(
            "Max Payout Count",
            payouts_ok,
            f"Payouts used: {payout_count} / {APEX_MAX_PAYOUTS}",
            "breach" if not payouts_ok else "ok",
        )
    )

    cap_ok = True
    cap_message = "All recorded payouts are within cap schedule"
    for idx, payout in enumerate(payouts):
        if idx >= len(APEX_PAYOUT_CAPS_50K):
            cap_ok = False
            cap_message = "More payouts recorded than cap schedule allows"
            break
        cap = APEX_PAYOUT_CAPS_50K[idx]
        if payout.amount > cap:
            cap_ok = False
            cap_message = f"Payout #{idx + 1} is ${payout.amount:.2f}, cap is ${cap:.2f}"
            break

    next_cap = APEX_PAYOUT_CAPS_50K[payout_count] if payout_count < len(APEX_PAYOUT_CAPS_50K) else Decimal("0.00")
    if cap_ok and payout_count < len(APEX_PAYOUT_CAPS_50K):
        cap_message = f"Next payout cap: ${next_cap:.2f}"

    checks.append(
        _check(
            "Payout Cap Schedule",
            cap_ok,
            cap_message,
            "breach" if not cap_ok else "ok",
        )
    )

    last_payout_date = payouts[-1].payout_date if payouts else None
    payout_window_day_nets = {
        day: amount
        for day, amount in day_nets.items()
        if (last_payout_date is None or day > last_payout_date)
    }
    payout_window_days = len(payout_window_day_nets)
    payout_window_net = sum(payout_window_day_nets.values(), Decimal("0.00"))
    payout_eligible = payout_window_days >= APEX_PAYOUT_MIN_DAYS and payout_window_net >= APEX_PAYOUT_MIN_PROFIT

    checks.append(
        _check(
            "Payout Eligibility",
            payout_eligible,
            (
                f"Since last payout: {payout_window_days} trading day(s), "
                f"net ${payout_window_net:.2f} (need {APEX_PAYOUT_MIN_DAYS} days and ${APEX_PAYOUT_MIN_PROFIT:.2f})"
            ),
            "ok" if payout_eligible else "warn",
        )
    )

    checks.append(
        _check(
            "Broker",
            account.broker == Broker.TRADOVATE,
            f"Configured broker: {account.get_broker_display()}",
            "warn" if account.broker != Broker.TRADOVATE else "ok",
        )
    )

    checks.append(
        _check(
            "Funded Snapshot",
            True,
            f"Trading days: {trading_days}, net PnL: ${net_pnl:.2f}",
            "ok",
        )
    )

    return checks


def _profit_target_for_account(account_size):
    if account_size == Decimal("50000") or account_size == Decimal("50000.00"):
        return APEX_50K_PROFIT_TARGET
    return Decimal("0.00")


def _build_day_nets(trades):
    day_nets = defaultdict(lambda: Decimal("0.00"))
    for trade in trades:
        day_nets[trade.trade_date] += trade.net_pnl
    return day_nets


def _check(name, passed, detail, level):
    return {
        "name": name,
        "passed": passed,
        "detail": detail,
        "level": level,
    }
