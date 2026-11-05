from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

from app.services.notification_service import (
    notify_all_teachers,
)

from app.schemas.admin_circular import (
    AdminCircularCreate,
    AdminCircularUpdate,
    AdminCircularStatusUpdate,
)


router = APIRouter(
    prefix="/admin/circulars",
    tags=["Admin Circulars"],
)


ALLOWED_AUDIENCES = {
    "ALL",
    "TEACHER",
    "PARENT",
    "CLASS",
}


# =========================================================
# HELPER
# =========================================================

def validate_audience(
    audience: str,
    class_id: int | None,
    db: Session,
):
    normalized_audience = (
        audience.strip().upper()
    )

    if normalized_audience not in ALLOWED_AUDIENCES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Audience must be ALL, "
                "TEACHER, PARENT or CLASS"
            ),
        )

    # CLASS circular requires class_id
    if normalized_audience == "CLASS":
        if not class_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "class_id is required "
                    "when audience is CLASS"
                ),
            )

        school_class = db.execute(
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

                LIMIT 1
                """
            ),
            {
                "class_id": class_id,
            },
        ).mappings().first()

        if not school_class:
            raise HTTPException(
                status_code=404,
                detail="Class not found",
            )

        if not bool(
            school_class["is_active"]
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot publish circular "
                    "to an inactive class"
                ),
            )

        return (
            normalized_audience,
            class_id,
        )

    # Non-class audience should not store class id
    return (
        normalized_audience,
        None,
    )


# =========================================================
# GET ALL CIRCULARS
# =========================================================

@router.get("")
def get_admin_circulars(
    search: str | None = None,
    category: str | None = None,
    audience: str | None = None,

    is_active: bool | None = Query(
        default=None
    ),

    page: int = Query(
        default=1,
        ge=1,
    ),

    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),

    db: Session = Depends(get_db),
):
    try:
        where_sql = """
            FROM circulars AS c

            LEFT JOIN school_classes AS sc
                ON sc.id = c.class_id

            WHERE 1 = 1
        """

        params = {}

        # -----------------------------------------
        # SEARCH
        # -----------------------------------------

        if search:
            where_sql += """
                AND (
                    c.title LIKE :search
                    OR c.description LIKE :search
                    OR c.category LIKE :search
                )
            """

            params["search"] = (
                f"%{search.strip()}%"
            )

        # -----------------------------------------
        # CATEGORY
        # -----------------------------------------

        if category:
            where_sql += """
                AND c.category = :category
            """

            params["category"] = (
                category.strip()
            )

        # -----------------------------------------
        # AUDIENCE
        # -----------------------------------------

        if audience:
            normalized_audience = (
                audience.strip().upper()
            )

            if (
                normalized_audience
                not in ALLOWED_AUDIENCES
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid audience",
                )

            where_sql += """
                AND c.audience = :audience
            """

            params["audience"] = (
                normalized_audience
            )

        # -----------------------------------------
        # STATUS
        # -----------------------------------------

        if is_active is not None:
            where_sql += """
                AND c.is_active = :is_active
            """

            params["is_active"] = (
                is_active
            )

        # -----------------------------------------
        # TOTAL
        # -----------------------------------------

        total = db.execute(
            text(
                f"""
                SELECT COUNT(*)
                {where_sql}
                """
            ),
            params,
        ).scalar() or 0

        # -----------------------------------------
        # PAGINATION
        # -----------------------------------------

        offset = (
            page - 1
        ) * page_size

        query_params = {
            **params,
            "limit": page_size,
            "offset": offset,
        }

        # -----------------------------------------
        # LIST
        # -----------------------------------------

        sql = f"""
            SELECT
                c.id,
                c.title,
                c.category,
                c.description,
                c.published_date,
                c.audience,
                c.class_id,
                c.attachment_url,
                c.created_by,
                c.is_active,
                c.created_at,
                c.updated_at,

                sc.name AS class_name,
                sc.section AS class_section,
                sc.academic_year

            {where_sql}

            ORDER BY
                c.published_date DESC,
                c.id DESC

            LIMIT :limit
            OFFSET :offset
        """

        rows = db.execute(
            text(sql),
            query_params,
        ).mappings().all()

        circulars = []

        for row in rows:
            circulars.append(
                {
                    "id":
                        row["id"],

                    "title":
                        row["title"],

                    "category":
                        row["category"],

                    "description":
                        row["description"],

                    "published_date":
                        row["published_date"],

                    "audience":
                        row["audience"],

                    "class_id":
                        row["class_id"],

                    "class": (
                        {
                            "id":
                                row["class_id"],

                            "name":
                                row["class_name"],

                            "section":
                                row[
                                    "class_section"
                                ],

                            "academic_year":
                                row[
                                    "academic_year"
                                ],
                        }
                        if row["class_id"]
                        else None
                    ),

                    "attachment_url":
                        row[
                            "attachment_url"
                        ],

                    "created_by":
                        row["created_by"],

                    "is_active":
                        bool(
                            row["is_active"]
                        ),

                    "created_at":
                        row["created_at"],

                    "updated_at":
                        row["updated_at"],
                }
            )

        total_pages = (
            (total + page_size - 1)
            // page_size
        )

        return {
            "success": True,
            "data": circulars,

            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next":
                    page < total_pages,
                "has_previous":
                    page > 1,
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin circular list error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load circulars"
            ),
        )

# =========================================================
# GET SINGLE CIRCULAR
# =========================================================

@router.get("/{circular_id}")
def get_admin_circular(
    circular_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                SELECT
                    c.id,
                    c.title,
                    c.category,
                    c.description,
                    c.published_date,
                    c.audience,
                    c.class_id,
                    c.attachment_url,
                    c.created_by,
                    c.is_active,
                    c.created_at,
                    c.updated_at,

                    sc.name AS class_name,
                    sc.section AS class_section,
                    sc.academic_year

                FROM circulars AS c

                LEFT JOIN school_classes AS sc
                    ON sc.id = c.class_id

                WHERE c.id = :circular_id

                LIMIT 1
                """
            ),
            {
                "circular_id":
                    circular_id,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Circular not found",
            )

        return {
            "success": True,
            "data": {
                "id":
                    row["id"],

                "title":
                    row["title"],

                "category":
                    row["category"],

                "description":
                    row["description"],

                "published_date":
                    row["published_date"],

                "audience":
                    row["audience"],

                "class_id":
                    row["class_id"],

                "class": (
                    {
                        "id":
                            row["class_id"],

                        "name":
                            row[
                                "class_name"
                            ],

                        "section":
                            row[
                                "class_section"
                            ],

                        "academic_year":
                            row[
                                "academic_year"
                            ],
                    }
                    if row["class_id"]
                    else None
                ),

                "attachment_url":
                    row[
                        "attachment_url"
                    ],

                "created_by":
                    row["created_by"],

                "is_active":
                    bool(
                        row["is_active"]
                    ),

                "created_at":
                    row["created_at"],

                "updated_at":
                    row["updated_at"],
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin circular detail error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load circular"
            ),
        )


# =========================================================
# CREATE CIRCULAR
# =========================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_admin_circular(
    payload: AdminCircularCreate,
    db: Session = Depends(get_db),
):
    try:
        audience, class_id = (
            validate_audience(
                payload.audience,
                payload.class_id,
                db,
            )
        )

        title = (
            payload.title.strip()
        )

        category = (
            payload.category.strip()
        )

        description = (
            payload.description.strip()
        )

        attachment_url = (
            payload.attachment_url.strip()
            if payload.attachment_url
            else None
        )

        # -----------------------------------------
        # CHECK CREATED BY USER
        # -----------------------------------------

        if payload.created_by:
            user = db.execute(
                text(
                    """
                    SELECT id

                    FROM users

                    WHERE id = :user_id

                    LIMIT 1
                    """
                ),
                {
                    "user_id":
                        payload.created_by,
                },
            ).first()

            if not user:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Created by user "
                        "not found"
                    ),
                )

        # -----------------------------------------
        # INSERT
        # -----------------------------------------

        result = db.execute(
            text(
                """
                INSERT INTO circulars
                (
                    title,
                    category,
                    description,
                    published_date,
                    audience,
                    class_id,
                    attachment_url,
                    created_by,
                    is_active
                )

                VALUES
                (
                    :title,
                    :category,
                    :description,
                    :published_date,
                    :audience,
                    :class_id,
                    :attachment_url,
                    :created_by,
                    :is_active
                )
                """
            ),
            {
                "title":
                    title,

                "category":
                    category,

                "description":
                    description,

                "published_date":
                    payload.published_date,

                "audience":
                    audience,

                "class_id":
                    class_id,

                "attachment_url":
                    attachment_url,

                "created_by":
                    payload.created_by,

                "is_active":
                    payload.is_active,
            },
        )

        circular_id = (
            result.lastrowid
        )

        # Teachers follow circulars addressed to them or to all.
        # Emitted inside the same transaction and never allowed to
        # fail the circular creation.
        if audience in ("ALL", "TEACHER"):
            notify_all_teachers(
                db=db,
                title="New Circular",
                message=title,
                notification_type="CIRCULAR",
                reference_id=circular_id,
                link="/teacher/circulars",
            )

        db.commit()

        return {
            "success": True,
            "message":
                "Circular created successfully",
            "data": {
                "id":
                    circular_id,

                "title":
                    title,

                "category":
                    category,

                "published_date":
                    payload.published_date,

                "audience":
                    audience,

                "class_id":
                    class_id,

                "is_active":
                    payload.is_active,
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Create circular error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create circular"
            ),
        )


# =========================================================
# UPDATE CIRCULAR
# =========================================================

@router.put("/{circular_id}")
def update_admin_circular(
    circular_id: int,
    payload: AdminCircularUpdate,
    db: Session = Depends(get_db),
):
    try:
        existing = db.execute(
            text(
                """
                SELECT id

                FROM circulars

                WHERE id = :circular_id

                LIMIT 1
                """
            ),
            {
                "circular_id":
                    circular_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Circular not found",
            )

        audience, class_id = (
            validate_audience(
                payload.audience,
                payload.class_id,
                db,
            )
        )

        attachment_url = (
            payload.attachment_url.strip()
            if payload.attachment_url
            else None
        )

        db.execute(
            text(
                """
                UPDATE circulars

                SET
                    title = :title,

                    category = :category,

                    description = :description,

                    published_date =
                        :published_date,

                    audience = :audience,

                    class_id = :class_id,

                    attachment_url =
                        :attachment_url

                WHERE id = :circular_id
                """
            ),
            {
                "title":
                    payload.title.strip(),

                "category":
                    payload.category.strip(),

                "description":
                    payload.description.strip(),

                "published_date":
                    payload.published_date,

                "audience":
                    audience,

                "class_id":
                    class_id,

                "attachment_url":
                    attachment_url,

                "circular_id":
                    circular_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Circular updated successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Update circular error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update circular"
            ),
        )


# =========================================================
# ACTIVATE / DEACTIVATE
# =========================================================

@router.patch(
    "/{circular_id}/status"
)
def update_admin_circular_status(
    circular_id: int,
    payload: AdminCircularStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        existing = db.execute(
            text(
                """
                SELECT id

                FROM circulars

                WHERE id = :circular_id

                LIMIT 1
                """
            ),
            {
                "circular_id":
                    circular_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Circular not found",
            )

        db.execute(
            text(
                """
                UPDATE circulars

                SET is_active =
                    :is_active

                WHERE id =
                    :circular_id
                """
            ),
            {
                "is_active":
                    payload.is_active,

                "circular_id":
                    circular_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Circular activated successfully"
                if payload.is_active
                else
                "Circular deactivated successfully"
            ),
            "data": {
                "id":
                    circular_id,

                "is_active":
                    payload.is_active,
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Circular status error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "circular status"
            ),
        )


# =========================================================
# DELETE CIRCULAR
# =========================================================

@router.delete("/{circular_id}")
def delete_admin_circular(
    circular_id: int,
    db: Session = Depends(get_db),
):
    try:
        existing = db.execute(
            text(
                """
                SELECT id

                FROM circulars

                WHERE id = :circular_id

                LIMIT 1
                """
            ),
            {
                "circular_id":
                    circular_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Circular not found",
            )

        db.execute(
            text(
                """
                DELETE FROM circulars

                WHERE id =
                    :circular_id
                """
            ),
            {
                "circular_id":
                    circular_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "Circular deleted successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Delete circular error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete circular"
            ),
        )