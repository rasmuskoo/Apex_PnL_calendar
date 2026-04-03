import calendar
from collections import defaultdict
from decimal import Decimal


def build_month_grid(year: int, month: int):
    cal = calendar.Calendar(firstweekday=0)
    return cal.monthdatescalendar(year, month)


def day_and_trade_streaks(trades):
    by_day = defaultdict(Decimal)
    for trade in trades.order_by("trade_date"):
        by_day[trade.trade_date] += trade.net_pnl

    day_results = []
    for day in sorted(by_day.keys()):
        if by_day[day] > 0:
            day_results.append(1)
        elif by_day[day] < 0:
            day_results.append(-1)

    trade_results = []
    for trade in trades.order_by("trade_date", "id"):
        if trade.net_pnl > 0:
            trade_results.append(1)
        elif trade.net_pnl < 0:
            trade_results.append(-1)

    return {
        "day": _streak_bundle(day_results),
        "trade": _streak_bundle(trade_results),
    }


def _streak_bundle(series):
    current_win = _tail_streak(series, 1)
    current_loss = _tail_streak(series, -1)
    best_win = _best_streak(series, 1)
    best_loss = _best_streak(series, -1)
    return {
        "current_win": current_win,
        "current_loss": current_loss,
        "best_win": best_win,
        "best_loss": best_loss,
    }


def _tail_streak(series, direction):
    streak = 0
    for value in reversed(series):
        if value == direction:
            streak += 1
        else:
            break
    return streak


def _best_streak(series, direction):
    best = 0
    current = 0
    for value in series:
        if value == direction:
            current += 1
            if current > best:
                best = current
        else:
            current = 0
    return best
