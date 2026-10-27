from pydantic import BaseModel
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
    id: Optional[str] = None
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

class TesdaData(BaseModel):
    id: Optional[str] = None
    member_id: Optional[int] = None
    uli: Optional[str] = None
    mothers_maiden: Optional[MothersMaiden] = None
    diploma: Optional[Degree] = None
    short_course: Optional[ShortCourse] = None
    enrollment_status: Optional[str] = None
    date_encoded: Optional[str] = None
    date_updated: Optional[str] = None

class TesdaResponsePayload(BaseModel):
    status: bool
    message: Optional[str] = None
    data: Optional[TesdaData] = None
    error_code: Optional[str] = None
    enrollment_id: Optional[int] = 0
