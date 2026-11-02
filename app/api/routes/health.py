from fastapi import APIRouter, Depends
from app.db.database import get_db_connection

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check():
    """
    Basic health check that confirms the API is running.
    """
    return {"status": "ok", "message": "Tuloy API is running."}

@router.get("/health/db")
def db_health_check(db = Depends(get_db_connection)):
    """
    Health check that confirms database connectivity.
    """
    try:
        # Simple test query to ensure DB is responsive
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "details": str(e)}
