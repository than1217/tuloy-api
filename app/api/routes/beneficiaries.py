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

@router.post("/VerifyMemberBene")
def match_user(user: UserInput, current_user: dict = Depends(get_current_user), db = Depends(get_db_connection)):
    cursor = db.cursor(dictionary=True)
    
    optional_filters = {
        "middle_name": user.middle_name,
        "sex": user.sex,
        "member_id": user.member_id,
        "household_id": user.household_id,
        "lrn": user.lrn,
        "pcn": user.pcn,
        "geocode": user.geocode,
    }
    optional_filter_columns = {
        "middle_name": "middle_name",
        "sex": "sex_id",
        "member_id": "member_id",
        "household_id": "listahanan_id",
        "lrn": "lrn",
        "pcn": "philsys",
        "geocode": "bgy_psgc_code",
    }
    
    try:
        # 2. Query the source table
        select_query = r"""
            SELECT * FROM vw_verify_member_bene 
            WHERE match_keys = UNHEX(MD5(CONCAT_WS('/', 
                UPPER(TRIM(REGEXP_REPLACE(%s, '\\s+', ' '))),
                UPPER(TRIM(REGEXP_REPLACE(%s, '\\s+', ' '))), 
                %s
            )))
        """
        query_params = [user.first_name, user.last_name, user.date_of_birth]
        for field, value in optional_filters.items():
            if value is not None:
                select_query += f" AND {optional_filter_columns[field]} = %s"
                query_params.append(value)

        cursor.execute(select_query, tuple(query_params))
        results = cursor.fetchall()
        
        row_count = len(results)
        
        # 3. Check the conditions
        if row_count == 0:
            return {"status": "Not Found", "tuloy_id": None, "member_id": None}
            
        elif row_count >= 2:
            return {"status": "Multiple Match Found", "tuloy_id": None, "member_id": None}
            
        elif row_count == 1:
            return {
                "status": "Matched",
                "tuloy_id": results[0].get("tuloy_id"),
                "member_id": results[0].get("member_id"),
            }
            
    except Error as e:
        logger.exception("Database error during beneficiary verification")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()

@router.get("/GetEligibleBene")
def get_eligible_bene(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT `first_name`,`middle_name`,`last_name`,
            `date_of_birth`,`sex_id`,`member_id`,`listahanan_id`,
            `lrn`,`philsys`,`grade_level`,
            `region_name`,`barangay_name`,`client_status`,`roster_status`, `tuloy_id` 
            FROM vw_unmatched_member_bene """ \
            "LIMIT %s OFFSET %s",
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
            custom_encoder={bytes: lambda value: value.hex()},
        )
    except Error as e:
        logger.exception("Database error while retrieving eligible beneficiaries")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()

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

@router.get("/GetValidatedEnrollees")
def get_validated_enrollees(
    agency: Optional[str] = Query(None, description="Filter by agency (CHED or TESDA)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """
    Retrieves the current validated student enrollees for both CHED and TESDA.
    Returns: agency_name, tuloy_id, member_id, enrollment_details (json), created_at, updated_at
    """
    cursor = db.cursor(dictionary=True)
    
    if agency:
        agency = agency.upper()
        if agency not in ["CHED", "TESDA"]:
            raise HTTPException(status_code=400, detail="Agency must be either CHED or TESDA")
            
        query = "SELECT * FROM vw_unified_matched_enrollment WHERE agency_name = %s LIMIT %s OFFSET %s"
        params = (agency, limit + 1, offset)
    else:
        query = "SELECT * FROM vw_unified_matched_enrollment LIMIT %s OFFSET %s"
        params = (limit + 1, offset)
    
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        has_more = len(rows) > limit
        actual_rows = rows[:limit]
        
        response_data = []
        for row in actual_rows:
            details = row.get('enrollment_details')
            if isinstance(details, str):
                import json
                try:
                    details = json.loads(details)
                except json.JSONDecodeError:
                    pass
                
            # Filter out None values to keep the JSON clean
            details = {k: v for k, v in details.items() if v is not None}
            
            response_data.append({
                "agency_name": agency,
                "tuloy_id": row['tuloy_id'],
                "member_id": row['member_id'],
                "enrollment_details": details,
                "created_at": str(row['created_at']) if row['created_at'] else None,
                "updated_at": str(row['updated_at']) if row['updated_at'] else None
            })
            
        return {
            "status": True, 
            "data": response_data,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None
        }
        
    except Error as e:
        logger.exception("Database error while fetching validated enrollees")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
