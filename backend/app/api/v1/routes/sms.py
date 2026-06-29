from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.models import SmsNotification
from backend.app.db.session import get_db
from backend.app.schemas.sms import SmsNotificationCreate, SmsNotificationRead, SmsSceneRead, SmsSendRequest
from backend.app.services.sms import AliyunSmsClient, SmsNotificationService, SmsSendResult, SUPPORTED_SMS_SCENES

router = APIRouter()


def _get_notification(db: Session, notification_id: str) -> SmsNotification:
    notification = db.query(SmsNotification).filter(SmsNotification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMS notification not found")
    return notification


@router.get("/scenes", response_model=list[SmsSceneRead])
async def list_sms_scenes() -> list[SmsSceneRead]:
    return [SmsSceneRead(scene=scene, description=description) for scene, description in SUPPORTED_SMS_SCENES.items()]


@router.post("/send", response_model=SmsSendResult)
async def send_sms(payload: SmsSendRequest) -> SmsSendResult:
    return await AliyunSmsClient().send_template_sms(
        payload.phone,
        payload.template_params,
        template_code=payload.template_code,
    )


@router.post("/notifications", response_model=SmsNotificationRead, status_code=status.HTTP_201_CREATED)
async def create_sms_notification(
    payload: SmsNotificationCreate,
    db: Session = Depends(get_db),
) -> SmsNotification:
    return await SmsNotificationService().create_and_send(
        db,
        scene=payload.scene,
        phone=payload.phone,
        user_id=payload.user_id,
        payload=payload.payload,
        template_code=payload.template_code,
    )


@router.get("/notifications", response_model=list[SmsNotificationRead])
async def list_sms_notifications(
    user_id: str | None = None,
    scene: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SmsNotification]:
    query = db.query(SmsNotification)
    if user_id:
        query = query.filter(SmsNotification.user_id == user_id)
    if scene:
        query = query.filter(SmsNotification.scene == scene)
    if status_filter:
        query = query.filter(SmsNotification.status == status_filter)
    return query.order_by(SmsNotification.created_at.desc()).limit(limit).all()


@router.post("/notifications/{notification_id}/retry", response_model=SmsNotificationRead)
async def retry_sms_notification(
    notification_id: str,
    db: Session = Depends(get_db),
) -> SmsNotification:
    notification = _get_notification(db, notification_id)
    return await SmsNotificationService().retry(db, notification)
