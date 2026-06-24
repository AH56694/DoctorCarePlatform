from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.services.sms import AliyunSmsClient, SmsSendResult

router = APIRouter()


class SmsRequest(BaseModel):
    phone: str = Field(min_length=5)
    template_params: dict[str, str] = {}


@router.post("/send", response_model=SmsSendResult)
async def send_sms(payload: SmsRequest) -> SmsSendResult:
    return await AliyunSmsClient().send_template_sms(payload.phone, payload.template_params)
