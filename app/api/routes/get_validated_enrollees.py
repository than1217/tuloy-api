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
                "agency_name": row.get('agency_name'),
                "tuloy_id": row.get('tuloy_id'),
                "member_id": row.get('member_id'),
                "enrollment_details": details,
                "created_at": str(row.get('created_at')) if row.get('created_at') else None,
                "updated_at": str(row.get('updated_at')) if row.get('updated_at') else None
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
