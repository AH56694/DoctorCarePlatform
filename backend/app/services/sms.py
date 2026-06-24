from dataclasses import dataclass

from backend.app.core.config import settings


@dataclass(frozen=True)
class SmsSendResult:
    status: str
    provider_message_id: str = ""
    detail: str = ""


class AliyunSmsClient:
    """Thin adapter for Aliyun SMS.

    The production implementation should call dysmsapi. The current skeleton keeps
    the boundary stable and returns a dry-run result when credentials are absent.
    """

    async def send_template_sms(self, phone: str, template_params: dict[str, str]) -> SmsSendResult:
        if not all(
            [
                settings.aliyun_sms_access_key_id,
                settings.aliyun_sms_access_key_secret,
                settings.aliyun_sms_sign_name,
                settings.aliyun_sms_template_code,
            ]
        ):
            return SmsSendResult(
                status="dry_run",
                detail=f"SMS to {phone} skipped because Aliyun credentials are not configured.",
            )
        return SmsSendResult(status="queued", provider_message_id="aliyun-placeholder")
