# auto-park

Text your bot a zone/space/duration the night before; it pays for parking on
[paywithpassport.com](https://paywithpassport.com/guest) at a fixed time
(default 9:05am) the next day.

Pieces (the `autopark` package lives under `src/`):
- `src/autopark/bot.py` — Telegram bot, receives `/park <zone> <space> <duration>` (or shorthand `"408 503 60"`), stores a job.
- `src/autopark/db.py` — SQLite job queue (`jobs.db`).
- `src/autopark/pay.py` — Playwright automation that drives the actual checkout flow.
- `src/autopark/scheduler.py` — long-running process: runs the bot + checks every 30s for jobs due to run. This is the `auto-park` entry point.
- `tests/` — pytest coverage for the pure logic (time parsing, shorthand, the job queue, config validation).

The app is a normal installable package: `auto-park` runs the scheduler and
`auto-park-pay` runs the manual payment tester. You can equivalently use
`python -m autopark` and `python -m autopark.pay`.

Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml`
+ `uv.lock`), and common tasks are wrapped in a `Makefile`:

```
make setup    # create .venv, install deps + Playwright browser
make run      # run the scheduler + bot
make pay ARGS="--zone 408 --space 503 --duration 15"   # manual dry run
make test     # pytest
make lint     # ruff check
make format   # ruff format
make lock     # refresh uv.lock + requirements.txt
make          # list all targets
```

No uv? A pinned `requirements.txt` is exported as a fallback:
`python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -e . --no-deps`.

## ⚠️ Before you trust this with real money

The selectors in `src/pay.py` were written from screenshots of the site, not
from inspecting the live DOM — field labels, the iframe structure of the
card form, and button text may not match exactly. **Test manually in dry-run
mode first**, see step 5 below. Until you've watched it succeed end-to-end
with `LIVE_MODE=false`, do not flip it to live.

## Setup

### 1. Install dependencies

Install [uv](https://docs.astral.sh/uv/) once (`brew install uv` or
`curl -LsSf https://astral.sh/uv/install.sh | sh`), then:

```bash
cd /Users/bellabao/Desktop/auto-park
make setup
```

That creates `.venv/`, installs everything from `uv.lock`, and downloads the
Playwright browser. (Under the hood: `uv sync --extra dev && uv run playwright
install chromium`.)

### 2. Create a Telegram bot

Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → follow
the prompts → copy the token it gives you.

### 3. Configure `.env`

```bash
cp .env.example .env
chmod 600 .env   # only you can read it — it will hold your card number
```

Fill in `TELEGRAM_BOT_TOKEN`, `PREFERRED_LOCATION` (must match the city text
shown in the "Multiple Results" dialog, e.g. `San Jose, CA`), `RECEIPT_EMAIL`,
and the `CARD_*` fields. Leave `TELEGRAM_CHAT_ID` blank for now, and leave
`LIVE_MODE=false`.

### 4. Get your chat_id and lock the bot down

```bash
make run
```

With `TELEGRAM_CHAT_ID` still blank, send your bot any message (e.g.
`/status`). The bot treats it as unauthorized and logs the id — find it in
`logs/auto-park.log`:

```bash
grep chat_id logs/auto-park.log | tail -1
# ... WARNING bot: Ignoring message from unauthorized chat_id=123456789
```

Put that number into `.env` as `TELEGRAM_CHAT_ID`, then `Ctrl+C` and re-run
`make run`. From now on the bot ignores any message from a chat_id other than
yours. (See "Known issues" below — `/start` intentionally only prints help, it
does **not** echo your chat_id.)

### 5. Dry-run the payment flow manually (do this before anything else)

```bash
cd /Users/bellabao/Desktop/auto-park
HEADLESS=false make pay ARGS="--zone 408 --space 503 --duration 60"
```

This opens a visible browser, fills the whole form including the card
fields, takes a screenshot in `screenshots/`, and **stops before the final
"PAY $X.XX" click**. Watch it click through and check the screenshot. If a
field doesn't get filled (label text mismatch, or the card form turns out to
be a same-origin/cross-origin iframe my `_find_input` fallback doesn't
catch), fix the matching `_find_input(...)` call or `_select_*` helper in
`src/autopark/pay.py` — the label-matching regexes are the most likely thing to
need adjusting.

Only once this looks right, repeat with a real small test and `--live` (this
**will** charge to your card):

```bash
make pay ARGS="--zone 408 --space 503 --duration 15 --live"
```

### 6. Try it through Telegram

With `auto-park` running, text your bot:

```
/park 408 503 60
```

or just `408 503 60`. It confirms the scheduled run time. `/status` shows the
pending job, `/cancel` removes it.

### 7. Flip to live mode

Once you've confirmed a real payment went through correctly in step 5, set
`LIVE_MODE=true` in `.env` and re-run `make run`. Now scheduled jobs will
actually submit payment, not just dry-run.

### 8. Make sure the Mac is actually awake at 9:05am

`make run` has to be running and the Mac has to be awake for a scheduled job
to fire. If you close the lid or it sleeps overnight, the job simply won't run
until you wake it up. Two options:

- Keep it plugged in with "Prevent automatic sleeping" on (System Settings →
  Battery/Energy), or
- Schedule an actual wake with `pmset`:
  ```bash
  sudo pmset repeat wakeorpoweron MTWRFSU 08:55:00
  ```

## Development

```bash
make test      # run the test suite (tests/)
make lint      # ruff check
make format    # ruff auto-format
make check     # lint + test together
```

(Or call the tools directly with `uv run pytest` / `uv run ruff ...`.) Config
for both tools lives in `pyproject.toml`. Tests use a throwaway SQLite file per
test (see `tests/conftest.py`) and never touch your real `jobs.db` or hit the
network.

Dependencies live in `pyproject.toml` and are locked in `uv.lock` (commit
both). To add or bump one, edit `pyproject.toml` then run `make lock` to
refresh `uv.lock` and the exported `requirements.txt`.

## Security notes

- `.env` holds your card number and CVV in plaintext, by your choice. It's
  gitignored — double check `git status` never shows it before any commit.
  Don't let it sync via iCloud Drive/Dropbox if this folder ever moves into
  a synced location.
- Only the Telegram `chat_id` you configure can schedule or cancel jobs —
  anyone else who messages the bot is ignored and logged.
- `LIVE_MODE=false` is the default; a scheduled job will only ever fill the
  form and screenshot it until you explicitly turn live mode on.
- The dry-run/success screenshots in `screenshots/` are full-page captures
  taken *after* the card fields are filled, so they contain your card number
  and CVV as an image. They're gitignored, but treat that folder as
  sensitive — see "Known issues".
