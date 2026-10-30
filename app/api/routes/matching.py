from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from mysql.connector import Error
from typing import Optional
import json

from app.db.database import get_db_connection
from app.core.logging_config import configure_logging
from app.schemas.schemas import UserInput, ChedResponsePayload, MothersMaiden, Degree, TesdaResponsePayload
from app.core.security import get_current_user


router = APIRouter(tags=['Matching'])

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


@router.get("/GetMatchedChedBene")
def get_matched_ched_records(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM vw_get_matched_CHED LIMIT %s OFFSET %s",
            (limit + 1, offset),
        )
        rows = cursor.fetchall()
        has_more = len(rows) > limit
        return jsonable_encoder(
            {
                "items": rows[:limit],
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
                "next_offset": offset + limit if has_more else None,
            },
            custom_encoder={bytes: lambda value: value.hex()}
        )
    except Error as e:
        logger.exception("Database error while retrieving matched CHED records")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()


@router.get("/GetMatchedTesdaBene")
def get_matched_tesda_records(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM vw_get_matched_TESDA LIMIT %s OFFSET %s",
            (limit + 1, offset),
        )
        rows = cursor.fetchall()
        has_more = len(rows) > limit
        
        # Parse JSON fields (now coming from enrollment_details in the view)
        import json
        for row in rows:
            if row.get('enrollment_details') and isinstance(row['enrollment_details'], str):
                try:
                    row['enrollment_details'] = json.loads(row['enrollment_details'])
                except json.JSONDecodeError:
                    pass

        return jsonable_encoder(
            {
                "items": rows[:limit],
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
                "next_offset": offset + limit if has_more else None,
            },
            custom_encoder={bytes: lambda value: value.hex()}
        )
    except Error as e:
        logger.exception("Database error while retrieving matched TESDA records")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()

