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
