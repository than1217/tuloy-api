from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from mysql.connector import Error
from fastapi_cache.decorator import cache
import os

from database import get_db_connection
from schemas import UserInput
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
            return {"status": "Not Found", "4ps_member_id": None}
            
        elif row_count >= 2:
            return {"status": "Multiple Match Found", "4ps_member_id": None}
            
        elif row_count == 1:
            return {
                "status": "Matched",
                "4ps_member_id": results[0].get("4ps_member_id"),
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
            "`bgy_psgc_code`,`barangay_name`,`client_status`,`roster_status`, `4ps_member_id` " \
            "FROM vw_verify_member_bene LIMIT %s OFFSET %s",
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
