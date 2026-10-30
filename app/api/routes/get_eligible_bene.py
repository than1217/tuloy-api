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
