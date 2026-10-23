from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from mysql.connector import Error
from fastapi_cache.decorator import cache
import os

from database import get_db_connection
from schemas import UserInput, ChedResponsePayload, MothersMaiden, Degree
from security import get_current_user

router = APIRouter(tags=["Beneficiaries"])

CACHE_EXPIRE_SECONDS = int(os.getenv("CACHE_EXPIRE_SECONDS", "1200"))

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
        print(f"\\n[ERROR] Database error during verification: {e}\\n")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()

@router.get("/GetEligibleBene")
@cache(expire=CACHE_EXPIRE_SECONDS, namespace="eligible-bene")
def get_eligible_bene(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT `first_name`,`middle_name`,`last_name`," \
            "`date_of_birth`,`sex_id`,`member_id`,`listahanan_id`," \
            "`lrn`,`philsys`,`grade_level`,`m_maiden_name`,`account_no`," \
            "`bgy_psgc_code`,`barangay_name`,`client_status`,`roster_status`, `tuloy_id` " \
            "FROM vw_verify_member_bene WHERE `tuloy_id` IN " \
            "(SELECT `tuloy_id` FROM enroll_matched_CHED_tbl) " \
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
        print(f"\\n[ERROR] Database error while retrieving eligible beneficiaries: {e}\\n")
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
        print(f"\\n[ERROR] Database error: {e}\\n")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()

