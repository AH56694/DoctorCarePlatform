import asyncio

from backend.app.core.config import settings
from backend.app.services.sms import AliyunSmsClient


def test_configured_placeholder_cannot_report_delivery(monkeypatch):
    for name in (
        "aliyun_sms_access_key_id", "aliyun_sms_access_key_secret",
        "aliyun_sms_sign_name", "aliyun_sms_template_code",
    ):
        monkeypatch.setattr(settings, name, "configured-for-test")
    result = asyncio.run(AliyunSmsClient().send_template_sms("13800000000", {}))
    assert result.status == "failed"
    assert result.provider_message_id == ""


def test_dry_run_does_not_expose_recipient_in_provider_detail(monkeypatch):
    monkeypatch.setattr(settings, "aliyun_sms_access_key_id", "")
    result = asyncio.run(AliyunSmsClient().send_template_sms("13800000000", {}))
    assert result.status == "dry_run"
    assert "13800000000" not in result.detail
