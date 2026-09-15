from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db

from app.schemas.admin_class import (
    AdminClassCreate,
    AdminClassUpdate,
    AdminClassStatusUpdate,
)


router = APIRouter(
    prefix="/admin/classes",
    tags=["Admin Classes"],
)


# -------------------------------------------------------
# GET ALL CLASSES
# -------------------------------------------------------

@router.get("")
def get_classes(
    db: Session = Depends(get_db),
):
    try:
        result = db.execute(
            text(
                """
                SELECT
                    id,
                    name,
                    section,
                    academic_year,
                    is_active
                FROM school_classes
                ORDER BY
                    academic_year DESC,
                    name ASC,
                    section ASC
                """
            )
        )

        rows = result.mappings().all()

        classes = []

        for row in rows:
            classes.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "section": row["section"],
                    "academic_year": row["academic_year"],
                    "is_active": bool(row["is_active"]),
                }
            )

        return {
            "success": True,
            "data": classes,
        }

    except Exception as e:
        print(
            "Admin classes list error:",
            str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load classes",
        )


# -------------------------------------------------------
# GET SINGLE CLASS
# -------------------------------------------------------

@router.get("/{class_id}")
def get_class(
    class_id: int,
    db: Session = Depends(get_db),
):
    try:
        result = db.execute(
            text(
                """
                SELECT
                    id,
                    name,
                    section,
                    academic_year,
                    is_active
                FROM school_classes
                WHERE id = :class_id
                """
            ),
            {
                "class_id": class_id,
            },
        )

        row = result.mappings().first()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found",
            )

        return {
            "success": True,
            "data": {
                "id": row["id"],
                "name": row["name"],
                "section": row["section"],
                "academic_year": row["academic_year"],
                "is_active": bool(
                    row["is_active"]
                ),
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin class detail error:",
            str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load class",
        )


# -------------------------------------------------------
# CREATE CLASS
# -------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_class(
    payload: AdminClassCreate,
    db: Session = Depends(get_db),
):
    try:
        # Check duplicate class
        duplicate = db.execute(
            text(
                """
                SELECT id
                FROM school_classes
                WHERE LOWER(name) = LOWER(:name)
                AND LOWER(section) = LOWER(:section)
                AND academic_year = :academic_year
                LIMIT 1
                """
            ),
            {
                "name": payload.name.strip(),
                "section": payload.section.strip(),
                "academic_year": (
                    payload.academic_year.strip()
                ),
            },
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This class, section and "
                    "academic year already exists"
                ),
            )

        result = db.execute(
            text(
                """
                INSERT INTO school_classes
                (
                    name,
                    section,
                    academic_year,
                    is_active
                )
                VALUES
                (
                    :name,
                    :section,
                    :academic_year,
                    :is_active
                )
                """
            ),
            {
                "name": payload.name.strip(),
                "section": payload.section.strip(),
                "academic_year": (
                    payload.academic_year.strip()
                ),
                "is_active": (
                    1
                    if payload.is_active
                    else 0
                ),
            },
        )

        db.commit()

        class_id = result.lastrowid

        return {
            "success": True,
            "message": (
                "Class created successfully"
            ),
            "data": {
                "id": class_id,
                "name": payload.name.strip(),
                "section": (
                    payload.section.strip()
                ),
                "academic_year": (
                    payload.academic_year.strip()
                ),
                "is_active": (
                    payload.is_active
                ),
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Admin create class error:",
            str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create class",
        )


# -------------------------------------------------------
# UPDATE CLASS
# -------------------------------------------------------

@router.put("/{class_id}")
def update_class(
    class_id: int,
    payload: AdminClassUpdate,
    db: Session = Depends(get_db),
):
    try:
        existing = db.execute(
            text(
                """
                SELECT id
                FROM school_classes
                WHERE id = :class_id
                """
            ),
            {
                "class_id": class_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found",
            )

        duplicate = db.execute(
            text(
                """
                SELECT id
                FROM school_classes
                WHERE LOWER(name) = LOWER(:name)
                AND LOWER(section) = LOWER(:section)
                AND academic_year = :academic_year
                AND id != :class_id
                LIMIT 1
                """
            ),
            {
                "name": payload.name.strip(),
                "section": payload.section.strip(),
                "academic_year": (
                    payload.academic_year.strip()
                ),
                "class_id": class_id,
            },
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another class with the "
                    "same name, section and "
                    "academic year already exists"
                ),
            )

        db.execute(
            text(
                """
                UPDATE school_classes

                SET
                    name = :name,
                    section = :section,
                    academic_year = :academic_year,
                    is_active = :is_active

                WHERE id = :class_id
                """
            ),
            {
                "name": payload.name.strip(),
                "section": payload.section.strip(),
                "academic_year": (
                    payload.academic_year.strip()
                ),
                "is_active": (
                    1
                    if payload.is_active
                    else 0
                ),
                "class_id": class_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Class updated successfully"
            ),
            "data": {
                "id": class_id,
                "name": payload.name.strip(),
                "section": (
                    payload.section.strip()
                ),
                "academic_year": (
                    payload.academic_year.strip()
                ),
                "is_active": (
                    payload.is_active
                ),
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Admin update class error:",
            str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update class",
        )


# -------------------------------------------------------
# ACTIVATE / DEACTIVATE CLASS
# -------------------------------------------------------

@router.patch("/{class_id}/status")
def update_class_status(
    class_id: int,
    payload: AdminClassStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        existing = db.execute(
            text(
                """
                SELECT id
                FROM school_classes
                WHERE id = :class_id
                """
            ),
            {
                "class_id": class_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found",
            )

        db.execute(
            text(
                """
                UPDATE school_classes

                SET is_active = :is_active

                WHERE id = :class_id
                """
            ),
            {
                "is_active": (
                    1
                    if payload.is_active
                    else 0
                ),
                "class_id": class_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Class activated successfully"
                if payload.is_active
                else
                "Class deactivated successfully"
            ),
            "data": {
                "id": class_id,
                "is_active": (
                    payload.is_active
                ),
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Admin class status error:",
            str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to update class status"
            ),
        )