from pydantic import BaseModel, Field
from typing import Optional

class UserCreate(BaseModel):
    username: str
    password: str

class UserInput(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    date_of_birth: str  # e.g., 'YYYY-MM-DD'
    sex: Optional[str] = None
    member_id: Optional[str] = None
    household_id: Optional[str] = None
    lrn: Optional[str] = None
    pcn: Optional[str] = None
    geocode: Optional[str] = None

class MothersMaiden(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None

class Degree(BaseModel):
    program_name: Optional[str] = None
    date_enrolled: Optional[str] = None
    program_duration: Optional[int] = None
    academic_year: Optional[str] = None
    year_level: Optional[int] = None
    semester: Optional[int] = None

class ChedData(BaseModel):
    id: str = Field(..., pattern="^4Ps-", description="TULOY ID must start with '4Ps-'")
    member_id: Optional[int] = None
    student_id: Optional[int] = None
    mothers_maiden: Optional[MothersMaiden] = None
    degree: Optional[Degree] = None
    enrollment_status: Optional[str] = None
    date_encoded: Optional[str] = None
    date_updated: Optional[str] = None

class ChedResponsePayload(BaseModel):
    status: bool
    message: Optional[str] = None
    data: Optional[ChedData] = None
    error_code: Optional[str] = None
    enrollment_id: Optional[int] = 0  # Required in db for FK to education_enrollment

class ShortCourse(BaseModel):
    program_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    training_status: Optional[str] = None

class TesdaEnrollment(BaseModel):
    date_encoded: Optional[str] = None
    date_updated: Optional[str] = None
    end_date: Optional[str] = None
    enrolled_at: Optional[str] = None
    qualification_code: Optional[str] = None
    qualification_name: Optional[str] = None
    start_date: Optional[str] = None
    status: Optional[str] = None

class TesdaLearner(BaseModel):
    birthdate: Optional[str] = None
    city_municipality: Optional[str] = None
    contact_no: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    member_id: Optional[int] = None
    middle_name: Optional[str] = None
    province: Optional[str] = None
    psgc_code: Optional[str] = None
    region: Optional[str] = None
    sex: Optional[str] = None
    suffix: Optional[str] = None
    tuloy_id: Optional[str] = Field(None, pattern="^4[pP]s-", description="TULOY ID must start with '4ps-' or '4Ps-'")
    user_uli: Optional[str] = None

class TesdaResponsePayload(BaseModel):
    status: Optional[str] = None
    matched: Optional[bool] = None
    match_method: Optional[str] = None
    learner: Optional[TesdaLearner] = None
    enrollments: Optional[list[TesdaEnrollment]] = None
    enrollment_id: Optional[int] = 0
