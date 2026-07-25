import pytest

from autopark import config


class TestRequireBotConfig:
    def test_passes_when_present(self, monkeypatch):
        monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
        monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "123")
        config.require_bot_config()  # should not raise

    def test_raises_and_names_missing(self, monkeypatch):
        monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
        monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "123")
        with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
            config.require_bot_config()


PAYMENT_FIELDS = (
    "PREFERRED_LOCATION",
    "RECEIPT_EMAIL",
    "CARD_NUMBER",
    "CARD_EXP",
    "CARD_CVV",
    "CARD_ZIP",
)


class TestRequirePaymentConfig:
    def test_passes_when_present(self, monkeypatch):
        for name in PAYMENT_FIELDS:
            monkeypatch.setattr(config, name, "x")
        config.require_payment_config()  # should not raise

    def test_raises_listing_all_missing(self, monkeypatch):
        for name in PAYMENT_FIELDS:
            monkeypatch.setattr(config, name, "")
        with pytest.raises(RuntimeError) as exc:
            config.require_payment_config()
        assert "CARD_NUMBER" in str(exc.value)
        assert "RECEIPT_EMAIL" in str(exc.value)
