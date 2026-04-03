# Apex PnL Calendar

Track your Apex trading performance in a calendar view, with built-in rule checks and copy-trading support.

This app is made for traders, not developers:
- Green/red calendar days for profit/loss at a glance
- Trade stats and streak summaries under the calendar
- Apex rule monitor (evaluation and funded checks)
- Copy trading groups with one lead account and automatic trade duplication

## Features

- Monthly PnL calendar (profit days in green, loss days in red)
- Filters by date range, account, and stage
- Summary metrics:
  - Net PnL
  - Trade win rate
  - Day and trade streaks
  - Average win/loss per trade and per day
- Apex-focused rule checks:
  - EOD drawdown and daily loss limits
  - Evaluation target/min-days/activation timing checks
  - Funded consistency and payout checks
- Copy trading:
  - Create copy groups
  - Mark one lead account per group
  - Trades entered on lead account copy to follower accounts

## Installation (GitHub)

### 1) Prerequisites

- Visual Studio Code installed
- Python 3.10+ installed
- Git installed

### 2) Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd YOUR-REPO
```

### 3) Create and activate a virtual environment

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 4) Install dependencies

```bash
pip install -r requirements.txt
```

### 5) Set up the database

```bash
python manage.py migrate
```

### 6) Run the app

```bash
python manage.py runserver
```

Open: `http://127.0.0.1:8000/`

## First Use

1. Open **Settings** (gear icon)
2. Add your Apex accounts
3. (Optional) Create copy-trading groups and select a lead account (star)
4. Start adding trades from the dashboard
