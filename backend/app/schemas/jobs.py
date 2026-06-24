from pydantic import BaseModel, Field


class JobPostingCreate(BaseModel):
    employer_id: str
    title: str = Field(min_length=2, max_length=120)
    city: str = ""
    care_level: str = ""
    budget_cents: int = 0
    description: str = ""


class JobPostingRead(JobPostingCreate):
    id: str
    status: str
