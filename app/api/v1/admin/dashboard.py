from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db


router = APIRouter(
    prefix="/admin/dashboard",
    tags=["Admin Dashboard"],
)


@router.get("/stats")
@router.get("", include_in_schema=False)
def get_dashboard_stats(
    db: Session = Depends(get_db),
):
    try:
        total_students = (
            db.execute(
                text("SELECT COUNT(*) FROM students")
            ).scalar()
            or 0
        )

        total_teachers = (
            db.execute(
                text("SELECT COUNT(*) FROM teacher_profiles")
            ).scalar()
            or 0
        )

        total_parents = (
            db.execute(
                text("SELECT COUNT(*) FROM parent_profiles")
            ).scalar()
            or 0
        )

        total_classes = (
            db.execute(
                text("SELECT COUNT(*) FROM school_classes")
            ).scalar()
            or 0
        )

        return {
            "success": True,
            "data": {
                "total_students": total_students,
                "total_teachers": total_teachers,
                "total_parents": total_parents,
                "total_classes": total_classes,
            },
        }

    except Exception as e:
        print("Dashboard stats error:", str(e))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load dashboard statistics",
        )
