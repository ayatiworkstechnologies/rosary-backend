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

from app.schemas.admin_school_event import (
    AdminSchoolEventCreate,
    AdminSchoolEventUpdate,
    AdminSchoolEventStatusUpdate,
)


router = APIRouter(
    prefix="/admin/calendar",
    tags=["Admin School Calendar"],
)


# ============================================================
# HELPER - VALIDATE DATES
# ============================================================

def validate_event_dates(
    start_date,
    end_date,
    start_time,
    end_time,
):
    if (
        end_date is not None
        and end_date < start_date
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "End date cannot be before "
                "start date"
            ),
        )

    effective_end_date = (
        end_date or start_date
    )

    if (
        effective_end_date == start_date
        and start_time is not None
        and end_time is not None
        and end_time < start_time
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "End time cannot be before "
                "start time"
            ),
        )


# ============================================================
# HELPER - VALIDATE AUDIENCE / CLASS
# ============================================================

def validate_event_audience(
    audience: str,
    class_id: int | None,
    db: Session,
):
    normalized_audience = (
        audience.strip().upper()
    )

    if not normalized_audience:
        raise HTTPException(
            status_code=400,
            detail="Audience is required",
        )

    # Specific class event
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
                    "Cannot assign event "
                    "to an inactive class"
                ),
            )

        return (
            normalized_audience,
            class_id,
        )

    # Global audiences do not need class_id
    return (
        normalized_audience,
        None,
    )


# ============================================================
# GET ALL EVENTS
# ============================================================

@router.get("")
def get_admin_school_events(
    search: str | None = None,
    event_type: str | None = None,
    audience: str | None = None,
    is_active: bool | None = Query(
        default=None
    ),
    db: Session = Depends(get_db),
):
    try:
        sql = """
            SELECT
                se.id,
                se.title,
                se.event_type,
                se.description,
                se.start_date,
                se.end_date,
                se.start_time,
                se.end_time,
                se.location,
                se.audience,
                se.class_id,
                se.created_by,
                se.is_active,
                se.created_at,
                se.updated_at,

                sc.name AS class_name,
                sc.section AS class_section,
                sc.academic_year,

                u.name AS creator_name

            FROM school_events AS se

            LEFT JOIN school_classes AS sc
                ON sc.id = se.class_id

            LEFT JOIN users AS u
                ON u.id = se.created_by

            WHERE 1 = 1
        """

        params = {}

        # SEARCH
        if search:
            sql += """
                AND (
                    se.title LIKE :search
                    OR se.description LIKE :search
                    OR se.location LIKE :search
                    OR se.event_type LIKE :search
                )
            """

            params["search"] = (
                f"%{search.strip()}%"
            )

        # EVENT TYPE
        if event_type:
            sql += """
                AND se.event_type =
                    :event_type
            """

            params["event_type"] = (
                event_type.strip()
            )

        # AUDIENCE
        if audience:
            sql += """
                AND se.audience =
                    :audience
            """

            params["audience"] = (
                audience.strip().upper()
            )

        # STATUS
        if is_active is not None:
            sql += """
                AND se.is_active =
                    :is_active
            """

            params["is_active"] = (
                is_active
            )

        sql += """
            ORDER BY
                se.start_date DESC,
                se.start_time DESC,
                se.id DESC
        """

        rows = db.execute(
            text(sql),
            params,
        ).mappings().all()

        events = []

        for row in rows:
            events.append(
                {
                    "id":
                        row["id"],

                    "title":
                        row["title"],

                    "event_type":
                        row["event_type"],

                    "description":
                        row["description"],

                    "start_date":
                        row["start_date"],

                    "end_date":
                        row["end_date"],

                    "start_time":
                        row["start_time"],

                    "end_time":
                        row["end_time"],

                    "location":
                        row["location"],

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

                    "created_by":
                        row["created_by"],

                    "creator_name":
                        row["creator_name"],

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

        return {
            "success": True,
            "total": len(events),
            "data": events,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Admin calendar list error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load "
                "school events"
            ),
        )


# ============================================================
# GET SINGLE EVENT
# ============================================================

@router.get("/{event_id}")
def get_admin_school_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                SELECT
                    se.id,
                    se.title,
                    se.event_type,
                    se.description,
                    se.start_date,
                    se.end_date,
                    se.start_time,
                    se.end_time,
                    se.location,
                    se.audience,
                    se.class_id,
                    se.created_by,
                    se.is_active,
                    se.created_at,
                    se.updated_at,

                    sc.name AS class_name,
                    sc.section AS class_section,
                    sc.academic_year,

                    u.name AS creator_name

                FROM school_events AS se

                LEFT JOIN school_classes AS sc
                    ON sc.id = se.class_id

                LEFT JOIN users AS u
                    ON u.id = se.created_by

                WHERE se.id = :event_id

                LIMIT 1
                """
            ),
            {
                "event_id": event_id,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=(
                    "School event not found"
                ),
            )

        return {
            "success": True,
            "data": {
                "id":
                    row["id"],

                "title":
                    row["title"],

                "event_type":
                    row["event_type"],

                "description":
                    row["description"],

                "start_date":
                    row["start_date"],

                "end_date":
                    row["end_date"],

                "start_time":
                    row["start_time"],

                "end_time":
                    row["end_time"],

                "location":
                    row["location"],

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

                "created_by":
                    row["created_by"],

                "creator_name":
                    row["creator_name"],

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
            "Admin event detail error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load "
                "school event"
            ),
        )


# ============================================================
# CREATE EVENT
# ============================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_admin_school_event(
    payload: AdminSchoolEventCreate,
    db: Session = Depends(get_db),
):
    try:
        # DATE VALIDATION
        validate_event_dates(
            payload.start_date,
            payload.end_date,
            payload.start_time,
            payload.end_time,
        )

        # AUDIENCE VALIDATION
        audience, class_id = (
            validate_event_audience(
                payload.audience,
                payload.class_id,
                db,
            )
        )

        # CREATED BY VALIDATION
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

        result = db.execute(
            text(
                """
                INSERT INTO school_events
                (
                    title,
                    event_type,
                    description,
                    start_date,
                    end_date,
                    start_time,
                    end_time,
                    location,
                    audience,
                    class_id,
                    created_by,
                    is_active
                )

                VALUES
                (
                    :title,
                    :event_type,
                    :description,
                    :start_date,
                    :end_date,
                    :start_time,
                    :end_time,
                    :location,
                    :audience,
                    :class_id,
                    :created_by,
                    :is_active
                )
                """
            ),
            {
                "title":
                    payload.title.strip(),

                "event_type":
                    payload.event_type.strip(),

                "description":
                    (
                        payload.description.strip()
                        if payload.description
                        else None
                    ),

                "start_date":
                    payload.start_date,

                "end_date":
                    payload.end_date,

                "start_time":
                    payload.start_time,

                "end_time":
                    payload.end_time,

                "location":
                    (
                        payload.location.strip()
                        if payload.location
                        else None
                    ),

                "audience":
                    audience,

                "class_id":
                    class_id,

                "created_by":
                    payload.created_by,

                "is_active":
                    payload.is_active,
            },
        )

        event_id = (
            result.lastrowid
        )

        db.commit()

        return {
            "success": True,
            "message":
                "School event created successfully",
            "data": {
                "id":
                    event_id,

                "title":
                    payload.title.strip(),

                "event_type":
                    payload.event_type.strip(),

                "start_date":
                    payload.start_date,

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
            "Create school event error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create "
                "school event"
            ),
        )


# ============================================================
# UPDATE EVENT
# ============================================================

@router.put("/{event_id}")
def update_admin_school_event(
    event_id: int,
    payload: AdminSchoolEventUpdate,
    db: Session = Depends(get_db),
):
    try:
        existing = db.execute(
            text(
                """
                SELECT id

                FROM school_events

                WHERE id = :event_id

                LIMIT 1
                """
            ),
            {
                "event_id":
                    event_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail=(
                    "School event not found"
                ),
            )

        validate_event_dates(
            payload.start_date,
            payload.end_date,
            payload.start_time,
            payload.end_time,
        )

        audience, class_id = (
            validate_event_audience(
                payload.audience,
                payload.class_id,
                db,
            )
        )

        db.execute(
            text(
                """
                UPDATE school_events

                SET
                    title =
                        :title,

                    event_type =
                        :event_type,

                    description =
                        :description,

                    start_date =
                        :start_date,

                    end_date =
                        :end_date,

                    start_time =
                        :start_time,

                    end_time =
                        :end_time,

                    location =
                        :location,

                    audience =
                        :audience,

                    class_id =
                        :class_id

                WHERE id =
                    :event_id
                """
            ),
            {
                "title":
                    payload.title.strip(),

                "event_type":
                    payload.event_type.strip(),

                "description":
                    (
                        payload.description.strip()
                        if payload.description
                        else None
                    ),

                "start_date":
                    payload.start_date,

                "end_date":
                    payload.end_date,

                "start_time":
                    payload.start_time,

                "end_time":
                    payload.end_time,

                "location":
                    (
                        payload.location.strip()
                        if payload.location
                        else None
                    ),

                "audience":
                    audience,

                "class_id":
                    class_id,

                "event_id":
                    event_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "School event updated successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Update school event error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "school event"
            ),
        )


# ============================================================
# ACTIVE / INACTIVE
# ============================================================

@router.patch(
    "/{event_id}/status"
)
def update_admin_school_event_status(
    event_id: int,
    payload: AdminSchoolEventStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        existing = db.execute(
            text(
                """
                SELECT id

                FROM school_events

                WHERE id = :event_id

                LIMIT 1
                """
            ),
            {
                "event_id":
                    event_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail=(
                    "School event not found"
                ),
            )

        db.execute(
            text(
                """
                UPDATE school_events

                SET is_active =
                    :is_active

                WHERE id =
                    :event_id
                """
            ),
            {
                "is_active":
                    payload.is_active,

                "event_id":
                    event_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "School event activated successfully"
                if payload.is_active
                else
                "School event deactivated successfully"
            ),
            "data": {
                "id":
                    event_id,

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
            "School event status error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "school event status"
            ),
        )


# ============================================================
# DELETE
# ============================================================

@router.delete("/{event_id}")
def delete_admin_school_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    try:
        existing = db.execute(
            text(
                """
                SELECT id

                FROM school_events

                WHERE id = :event_id

                LIMIT 1
                """
            ),
            {
                "event_id":
                    event_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail=(
                    "School event not found"
                ),
            )

        db.execute(
            text(
                """
                DELETE FROM school_events

                WHERE id = :event_id
                """
            ),
            {
                "event_id":
                    event_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message":
                "School event deleted successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Delete school event error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete "
                "school event"
            ),
        )