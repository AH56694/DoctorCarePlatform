from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.models import SmsNotification


SUPPORTED_SMS_SCENES: dict[str, str] = {
    "new_application": "护理方提交新应聘",
    "application_review": "患者审核应聘结果",
    "new_invitation": "患者发起反向邀约",
    "invitation_response": "护理方回应邀约",
    "new_message": "匹配会话收到新消息",
    "new_review": "收到新的服务评价",
    "verification_result": "身份或资质审核结果",
    "manual": "后台手动短信通知",
}


SCENE_DEFAULT_TEMPLATE_PARAMS: dict[str, dict[str, str]] = {
    "new_application": {"scene": "新应聘"},
    "application_review": {"scene": "应聘审核"},
    "new_invitation": {"scene": "新邀约"},
    "invitation_response": {"scene": "邀约回应"},
    "new_message": {"scene": "新消息"},
    "new_review": {"scene": "新评价"},
    "verification_result": {"scene": "审核结果"},
    "manual": {"scene": "平台通知"},
}


@dataclass(frozen=True)
class SmsSendResult:
    status: str
    provider_message_id: str = ""
    detail: str = ""


class AliyunSmsClient:
    """Thin adapter for Aliyun SMS.

    The production path can replace the placeholder branch with dysmsapi calls.
    When credentials are absent, calls become dry-run while preserving records.
    """

    async def send_template_sms(
        self,
        phone: str,
        template_params: dict[str, str],
        *,
        template_code: str | None = None,
    ) -> SmsSendResult:
        resolved_template = template_code or settings.aliyun_sms_template_code
        if not all(
            [
                settings.aliyun_sms_access_key_id,
                settings.aliyun_sms_access_key_secret,
                settings.aliyun_sms_sign_name,
                resolved_template,
            ]
        ):
            return SmsSendResult(
                status="dry_run",
                detail=f"SMS to {phone} skipped because Aliyun credentials are not configured.",
            )
        return SmsSendResult(status="sent", provider_message_id="aliyun-placeholder")


def build_template_params(scene: str, payload: dict[str, Any] | None = None) -> dict[str, str]:
    params: dict[str, str] = dict(SCENE_DEFAULT_TEMPLATE_PARAMS.get(scene, {"scene": scene}))
    for key, value in (payload or {}).items():
        if value is None:
            continue
        params[key] = str(value)
    return params


class SmsNotificationService:
    def __init__(self, client: AliyunSmsClient | None = None) -> None:
        self.client = client or AliyunSmsClient()

    async def create_and_send(
        self,
        db: Session,
        *,
        scene: str,
        phone: str,
        user_id: str | None = None,
        payload: dict[str, Any] | None = None,
        template_code: str | None = None,
    ) -> SmsNotification:
        if scene not in SUPPORTED_SMS_SCENES:
            scene = "manual"

        payload_data = dict(payload or {})
        template_params = build_template_params(scene, payload_data)
        notification = SmsNotification(
            user_id=user_id,
            scene=scene,
            phone=phone,
            template_code=template_code or settings.aliyun_sms_template_code,
            status="queued",
            payload={**payload_data, "template_params": template_params},
        )
        db.add(notification)
        db.flush()

        result = await self.client.send_template_sms(
            phone,
            template_params,
            template_code=notification.template_code,
        )
        notification.status = result.status
        notification.provider_message_id = result.provider_message_id
        notification.payload = {
            **(notification.payload or {}),
            "provider_detail": result.detail,
        }
        if result.status in {"sent", "dry_run"}:
            notification.sent_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
        return notification

    async def retry(self, db: Session, notification: SmsNotification) -> SmsNotification:
        payload = dict(notification.payload or {})
        template_params = payload.get("template_params") or build_template_params(notification.scene, payload)
        result = await self.client.send_template_sms(
            notification.phone,
            template_params,
            template_code=notification.template_code,
        )
        notification.status = result.status
        notification.provider_message_id = result.provider_message_id
        notification.payload = {
            **payload,
            "template_params": template_params,
            "provider_detail": result.detail,
            "retried_at": datetime.now(timezone.utc).isoformat(),
        }
        if result.status in {"sent", "dry_run"}:
            notification.sent_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
        return notification
