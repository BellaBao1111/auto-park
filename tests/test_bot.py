from datetime import datetime

import pytest

from autopark import bot, config


class TestParseTimeArg:
    def test_valid(self):
        assert bot._parse_time_arg("08:30") == (8, 30)
        assert bot._parse_time_arg("0:05") == (0, 5)
        assert bot._parse_time_arg("23:59") == (23, 59)

    @pytest.mark.parametrize("bad", ["", "8", "8:5", "0830", "8:30am", "24:00", "12:60", "-1:00"])
    def test_invalid_raises(self, bad):
        with pytest.raises(ValueError):
            bot._parse_time_arg(bad)


class TestNextRunAt:
    def test_defaults_to_configured_time_tomorrow(self, monkeypatch):
        monkeypatch.setattr(config, "RUN_HOUR", 9)
        monkeypatch.setattr(config, "RUN_MINUTE", 5)
        now = datetime(2026, 7, 24, 15, 0)

        assert bot._next_run_at(now) == datetime(2026, 7, 25, 9, 5)

    def test_explicit_time_later_today_stays_today(self):
        now = datetime(2026, 7, 24, 8, 0)
        assert bot._next_run_at(now, 8, 30) == datetime(2026, 7, 24, 8, 30)

    def test_explicit_time_already_passed_rolls_to_tomorrow(self):
        now = datetime(2026, 7, 24, 9, 0)
        assert bot._next_run_at(now, 8, 30) == datetime(2026, 7, 25, 8, 30)

    def test_explicit_time_equal_to_now_rolls_to_tomorrow(self):
        now = datetime(2026, 7, 24, 8, 30, 15)
        # target zeroes seconds -> 08:30:00 <= now (08:30:15), so rolls forward.
        assert bot._next_run_at(now, 8, 30) == datetime(2026, 7, 25, 8, 30)


class TestShorthandRegex:
    def test_matches_without_time(self):
        m = bot.SHORTHAND_RE.match("408 503 60")
        assert m.groups() == ("408", "503", "60", None)

    def test_matches_with_time(self):
        m = bot.SHORTHAND_RE.match("408 503 60 08:30")
        assert m.groups() == ("408", "503", "60", "08:30")

    def test_tolerates_surrounding_whitespace(self):
        m = bot.SHORTHAND_RE.match("  408 503 30  ")
        assert m.groups() == ("408", "503", "30", None)

    @pytest.mark.parametrize(
        "text",
        [
            "408 503 20",  # duration not in 15/30/45/60
            "408 503",  # missing duration
            "hello there",  # nonsense
            "408 503 60 830",  # malformed time
        ],
    )
    def test_rejects_bad_input(self, text):
        assert bot.SHORTHAND_RE.match(text) is None
