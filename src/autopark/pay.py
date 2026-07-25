"""
Playwright automation for paywithpassport.com/guest.

IMPORTANT: the selectors below are my best guess from screenshots of the
site, not from inspecting the live DOM. Before trusting this for a real
payment, run it manually in headed + dry-run mode and watch it click
through, e.g.:

    HEADLESS=false python -m autopark.pay --zone 408 --space 503 --duration 60

It will fill everything and stop right before the final "PAY $X.XX" click
(unless LIVE_MODE=true / --live is passed). Fix any selector that fails
before wiring it into the scheduler.
"""

import argparse
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PWTimeoutError

from . import config

log = logging.getLogger("pay")


@dataclass
class PayResult:
    success: bool
    message: str
    screenshot_path: str | None = None


def _shot(page: Page, name: str) -> str:
    config.SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = config.SCREENSHOT_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def _find_input(page: Page, label_pattern: str, timeout_ms: int = 8000):
    """Best-effort locator for a labeled input, searching main frame then
    any iframes (the card form may be a PCI-scoped iframe). This is a
    client-rendered SPA, so the element may not exist yet right after
    navigation/click - poll instead of checking once."""
    pattern = re.compile(label_pattern, re.IGNORECASE)
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        contexts = [page] + [f for f in page.frames if f != page.main_frame]
        for ctx in contexts:
            for get_locator in (ctx.get_by_label, ctx.get_by_placeholder):
                try:
                    loc = get_locator(pattern)
                    if loc.count() > 0:
                        return loc.first
                except Exception:
                    continue
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Could not find input matching /{label_pattern}/ after {timeout_ms}ms")
        page.wait_for_timeout(200)


def _select_location(page: Page, preferred_location: str):
    dialog = page.get_by_text("Multiple Results for Zone Number", exact=False)
    try:
        dialog.wait_for(state="visible", timeout=4000)
    except PWTimeoutError:
        return  # unambiguous zone, no dialog shown

    option = page.get_by_text(re.compile(re.escape(preferred_location), re.IGNORECASE))
    option.first.click()
    page.get_by_role("button", name=re.compile("^OK$", re.IGNORECASE)).click()


def _select_duration(page: Page, minutes: int):
    # Native <select> whose option values are the duration in minutes ("15",
    # "30", ...). Which durations are offered depends on the zone, so check the
    # live options first and fail fast with a clear message rather than letting
    # select_option time out for 30s when the requested one isn't available.
    dropdown = _find_input(page, "Duration")
    options = dropdown.evaluate(
        "el => Array.from(el.options).map(o => ({value: o.value, text: (o.textContent || '').trim()}))"
    )
    values = {o["value"] for o in options}
    if str(minutes) not in values:
        available = ", ".join(o["text"] for o in options if o["value"]) or "(none)"
        raise RuntimeError(
            f"Duration {minutes} min is not offered for this zone. Available: {available}"
        )
    dropdown.select_option(value=str(minutes))


def _click_continue(page: Page):
    button = page.get_by_role("button", name=re.compile("^Continue$", re.IGNORECASE))
    button.wait_for(state="visible", timeout=8000)
    button.click()


def run_payment(zone: str, space: str, duration_minutes: int) -> PayResult:
    """
    The site reveals fields progressively behind three separate "Continue"
    clicks: zone/location/space -> Continue -> duration appears -> Continue
    -> payment summary + email appears -> Continue -> payment method
    buttons appear. Verified against the live site.
    """
    config.require_payment_config()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.HEADLESS)
        page = browser.new_page()
        try:
            page.goto(config.PARKING_URL, wait_until="domcontentloaded")

            zone_input = _find_input(page, "Zone Number")
            zone_input.fill(zone)
            zone_input.press("Enter")

            _select_location(page, config.PREFERRED_LOCATION)

            space_input = _find_input(page, "Space Number")
            space_input.fill(space)
            _click_continue(page)

            _select_duration(page, duration_minutes)
            _click_continue(page)

            email_input = _find_input(page, "Receipt Email")
            email_input.fill(config.RECEIPT_EMAIL)
            _click_continue(page)

            card_button = page.get_by_role("button", name=re.compile("PAY WITH CARD", re.IGNORECASE))
            card_button.wait_for(state="visible", timeout=8000)
            card_button.click()

            _find_input(page, "Card Number").fill(config.CARD_NUMBER)
            _find_input(page, r"^Exp").fill(config.CARD_EXP)
            _find_input(page, r"^CVV").fill(config.CARD_CVV)
            _find_input(page, r"^Zip").fill(config.CARD_ZIP)

            pre_submit_shot = _shot(page, "pre_submit")

            if not config.LIVE_MODE:
                browser.close()
                return PayResult(
                    success=True,
                    message=(
                        "DRY RUN: form filled through card entry, did NOT submit. "
                        "Set LIVE_MODE=true in .env once you've verified this screenshot looks right."
                    ),
                    screenshot_path=pre_submit_shot,
                )

            page.get_by_role("button", name=re.compile(r"^PAY \$", re.IGNORECASE)).click()
            time.sleep(3)
            post_submit_shot = _shot(page, "post_submit")
            return PayResult(
                success=True,
                message="Payment submitted.",
                screenshot_path=post_submit_shot,
            )

        except Exception as exc:  # noqa: BLE001 - surface any failure with a screenshot
            log.exception("Payment automation failed")
            error_shot = None
            try:
                error_shot = _shot(page, "error")
            except Exception:
                pass
            return PayResult(success=False, message=f"Error: {exc}", screenshot_path=error_shot)
        finally:
            try:
                browser.close()
            except Exception:
                pass


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Manually test the parking payment automation")
    parser.add_argument("--zone", required=True)
    parser.add_argument("--space", required=True)
    parser.add_argument("--duration", type=int, required=True, choices=[15, 30, 45, 60])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="override .env and actually submit payment")
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="override .env and force a dry run (never submit), even if LIVE_MODE=true",
    )
    args = parser.parse_args()

    if args.live:
        config.LIVE_MODE = True
    elif args.dry_run:
        config.LIVE_MODE = False

    result = run_payment(args.zone, args.space, args.duration)
    print(f"success={result.success}")
    print(f"message={result.message}")
    print(f"screenshot={result.screenshot_path}")
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
