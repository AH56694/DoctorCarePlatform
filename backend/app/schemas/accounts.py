from pydantic import BaseModel, Field

RoleName = str


class UserRegister(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=80)
    initial_role: RoleName = "patient"


class UserLogin(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class RoleSwitchRequest(BaseModel):
    role: RoleName


class RoleCreateRequest(BaseModel):
    role: RoleName


class PatientProfileUpdate(BaseModel):
    real_name: str = Field(default="", max_length=80)
    id_number: str = Field(default="", max_length=64)
    basic_info: dict = Field(default_factory=dict)


class CaregiverProfileUpdate(BaseModel):
    real_name: str = Field(default="", max_length=80)
    id_number: str = Field(default="", max_length=64)
    bio: str = Field(default="", max_length=2000)
    is_available: bool = True
    experience_years: int = Field(default=0, ge=0, le=80)
    service_city: str = Field(default="", max_length=80)


class CertificationCreate(BaseModel):
    certificate_type: str = Field(min_length=1, max_length=80)
    file_url: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=1000)


class CertificationReview(BaseModel):
    review_status: str = Field(pattern="^(pending|approved|rejected)$")
    review_note: str = Field(default="", max_length=1000)


class UserRoleRead(BaseModel):
    id: str
    role: str
    is_active: bool
    verification_status: str


class PatientProfileRead(BaseModel):
    real_name: str = ""
    id_verified: bool = False
    verification_status: str = "pending"
    basic_info: dict = Field(default_factory=dict)


class CaregiverProfileRead(BaseModel):
    real_name: str = ""
    id_verified: bool = False
    verification_status: str = "pending"
    bio: str = ""
    is_available: bool = True
    experience_years: int = 0
    service_city: str = ""
    rating_avg: float = 0


class CertificationRead(BaseModel):
    id: str
    caregiver_profile_id: str
    certificate_type: str
    file_url: str
    description: str
    review_status: str
    review_note: str


class AccountRead(BaseModel):
    id: str
    phone: str
    display_name: str
    status: str
    active_role: str
    roles: list[UserRoleRead]
    patient_profile: PatientProfileRead | None = None
    caregiver_profile: CaregiverProfileRead | None = None
    certifications: list[CertificationRead] = Field(default_factory=list)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account: AccountRead
