from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from mysql.connector import Error
from typing import Optional
import json

from app.db.database import get_db_connection
from app.core.logging_config import configure_logging
from app.schemas.schemas import UserInput, ChedResponsePayload, MothersMaiden, Degree, TesdaResponsePayload
from app.core.security import get_current_user

router = APIRouter(tags=["Beneficiaries"])
logger = configure_logging()

@router.post("/PostEnrolleeMatchedTESDA")
def record_tesda_response(
    payload: TesdaResponsePayload, 
    current_user: dict = Depends(get_current_user), 
    db = Depends(get_db_connection)
):
    cursor = db.cursor()
    try:
        data = None
        enrollment_id = 0
        if payload.status and payload.message == "FOUND" and payload.data:
            data = payload.data
            if not data.id or len(data.id) > 50:
                raise HTTPException(
                    status_code=422,
                    detail="Matched TESDA data requires a TULOY ID of at most 50 characters.",
                )
            if data.member_id is None or not 1 <= data.member_id <= 4294967295:
                raise HTTPException(
                    status_code=422,
                    detail="Matched TESDA data requires a MEMBER ID between 1 and 4294967295.",
                )
            if data.uli and len(data.uli) > 50:
                raise HTTPException(
                    status_code=422,
                    detail="ULI exceeds the database limit of 50 characters.",
                )

            if payload.enrollment_id is not None:
                enrollment_id = payload.enrollment_id
            if not 0 <= enrollment_id <= 4294967295:
                raise HTTPException(
                    status_code=422,
                    detail="enrollment_id must be between 0 and 4294967295.",
                )

        insert_txn_query = """
            INSERT INTO matching_transaction_TESDA_tbl 
            (`tuloy_id`, `status`) 
            VALUES (%s, %s)
        """
        
        transaction_tuloy_id = ""
        if payload.data:
            if payload.data.id:
                transaction_tuloy_id = payload.data.id
                
        db_status = payload.message or ("FOUND" if payload.status else "NOT FOUND")
        
        cursor.execute(insert_txn_query, (
            transaction_tuloy_id,
            db_status
        ))
        txn_id = cursor.lastrowid
        
        if data:
            insert_data_query = """
                INSERT INTO enroll_matched_TESDA_tbl (
                    match_id, enrollment_id, `tuloy_id`, member_id, uli_id,
                    mm_first_name, mm_middle_name, mm_last_name,
                    diploma, short_course
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
            """
            
            date_encoded = (
                data.date_encoded.strip() or None if data.date_encoded else None
            )
            date_updated = (
                data.date_updated.strip() or None if data.date_updated else None
            )
            diploma_json = None
            if data.diploma is not None:
                diploma = data.diploma
                date_enrolled = (
                    diploma.date_enrolled.strip() or None
                    if diploma.date_enrolled
                    else None
                )
                diploma_json = json.dumps({
                    "program_name": diploma.program_name,
                    "date_enrolled": date_enrolled,
                    "program_duration": diploma.program_duration,
                    "academic_year": diploma.academic_year,
                    "year_level": diploma.year_level,
                    "semester": diploma.semester,
                    "enrollment_status": data.enrollment_status,
                    "date_encoded": date_encoded,
                    "date_updated": date_updated,
                })

            short_course_json = None
            if data.short_course is not None:
                course = data.short_course
                start_date = (
                    course.start_date.strip() or None
                    if course.start_date
                    else None
                )
                end_date = (
                    course.end_date.strip() or None
                    if course.end_date
                    else None
                )
                short_course_json = json.dumps({
                    "program_name": course.program_name,
                    "start_date": start_date,
                    "end_date": end_date,
                    "training_status": course.training_status,
                    "date_encoded": date_encoded,
                    "date_updated": date_updated,
                })

            mother_maiden = data.mothers_maiden
            
            cursor.execute(insert_data_query, (
                txn_id, enrollment_id, data.id, data.member_id, data.uli,
                mother_maiden.first_name if mother_maiden else None,
                mother_maiden.middle_name if mother_maiden else None,
                mother_maiden.last_name if mother_maiden else None,
                diploma_json, short_course_json
            ))
            
        db.commit()
        return {"message": "TESDA response recorded successfully."}
    except Error as e:
        db.rollback()
        logger.exception("Database error while recording TESDA response")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
