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

@router.post("/PostEnrolleeMatchedCHED")
def record_ched_response(
    payload: ChedResponsePayload, 
    current_user: dict = Depends(get_current_user), 
    db = Depends(get_db_connection)
):
    cursor = db.cursor()
    try:
        # 1. Insert into transaction status table
        insert_txn_query = """
            INSERT INTO matching_transaction_CHED_tbl 
            (`tuloy_id`, `status`) 
            VALUES (%s, %s)
        """
        
        member_id_str = ""
        if payload.data:
            if payload.data.id:
                member_id_str = str(payload.data.id)
            elif payload.data.member_id:
                member_id_str = str(payload.data.member_id)
                
        db_status = payload.message or ("FOUND" if payload.status else "NOT FOUND")
        
        cursor.execute(insert_txn_query, (
            member_id_str, 
            db_status
        ))
        txn_id = cursor.lastrowid
        
        # 2. Insert into data table if status is matched (or status == True and message == "FOUND")
        if payload.status and payload.message == "FOUND" and payload.data:
            insert_data_query = """
                INSERT INTO enroll_matched_CHED_tbl (
                    match_id, enrollment_id, `tuloy_id`, member_id, student_id,
                    mm_first_name, mm_middle_name, mm_last_name,
                    degree_program_name, degree_date_enrolled, degree_program_duration,
                    degree_academic_year, degree_year_level, degree_semester,
                    enrollment_status, date_encoded, date_updated
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
            """
            
            data = payload.data
            mmn = data.mothers_maiden or MothersMaiden()
            deg = data.degree or Degree()
            
            # Use 0 for enrollment_id if not present since it's NOT NULL
            # or pass it from a query string if desired
            enrollment_id = payload.enrollment_id if hasattr(payload, 'enrollment_id') else 0

            # Convert blank strings to None for date fields so MySQL handles them properly
            date_enrolled_val = deg.date_enrolled if deg.date_enrolled and deg.date_enrolled.strip() else None
            date_encoded_val = data.date_encoded if data.date_encoded and data.date_encoded.strip() else None
            date_updated_val = data.date_updated if data.date_updated and data.date_updated.strip() else None
            
            cursor.execute(insert_data_query, (
                txn_id, enrollment_id, data.id, data.member_id or 0, data.student_id,
                mmn.first_name, mmn.middle_name, mmn.last_name,
                deg.program_name, date_enrolled_val, deg.program_duration,
                deg.academic_year, deg.year_level, deg.semester,
                data.enrollment_status, date_encoded_val, date_updated_val
            ))
            
        db.commit()
        return {"message": "CHED response recorded successfully."}
    except Error as e:
        db.rollback()
        logger.exception("Database error while recording CHED response")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
