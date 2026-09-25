from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

from app.schemas.admin_parent_link import (
    AdminParentLinkCreate,
    AdminParentLinkUpdate,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin Parent Linking"],
)


# =========================================================
# GET PARENTS FOR DROPDOWN
# =========================================================

@router.get("/parent-options")
def get_admin_parents(
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    user_id,
                    phone,
                    alternate_phone,
                    occupation,
                    city,
                    state

                FROM parent_profiles

                ORDER BY user_id ASC
                """
            )
        ).mappings().all()

        parents = []

        for row in rows:
            parents.append(
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "phone": row["phone"],
                    "alternate_phone":
                        row["alternate_phone"],
                    "occupation":
                        row["occupation"],
                    "city": row["city"],
                    "state": row["state"],
                }
            )

        return {
            "success": True,
            "data": parents,
        }

    except Exception as e:
        print(
            "Admin parents error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load parents",
        )


# =========================================================
# GET ALL PARENT-STUDENT LINKS
# =========================================================

@router.get("/parent-links")
def get_parent_links(
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    ps.id,
                    ps.parent_user_id,
                    ps.student_id,
                    ps.relationship,
                    ps.created_at,

                    pp.phone AS parent_phone,

                    s.admission_no,
                    s.roll_no,
                    s.full_name,
                    s.gender,
                    s.class_id,
                    s.is_active AS student_active,

                    sc.name AS class_name,
                    sc.section,
                    sc.academic_year

                FROM parent_students AS ps

                LEFT JOIN parent_profiles AS pp
                    ON pp.user_id =
                       ps.parent_user_id

                INNER JOIN students AS s
                    ON s.id =
                       ps.student_id

                LEFT JOIN school_classes AS sc
                    ON sc.id =
                       s.class_id

                ORDER BY
                    s.full_name ASC,
                    ps.id ASC
                """
            )
        ).mappings().all()

        links = []

        for row in rows:
            links.append(
                {
                    "id": row["id"],

                    "parent_user_id":
                        row["parent_user_id"],

                    "parent": {
                        "user_id":
                            row[
                                "parent_user_id"
                            ],

                        "phone":
                            row[
                                "parent_phone"
                            ],
                    },

                    "student_id":
                        row["student_id"],

                    "student": {
                        "id":
                            row[
                                "student_id"
                            ],

                        "admission_no":
                            row[
                                "admission_no"
                            ],

                        "roll_no":
                            row[
                                "roll_no"
                            ],

                        "full_name":
                            row[
                                "full_name"
                            ],

                        "gender":
                            row[
                                "gender"
                            ],

                        "class_id":
                            row[
                                "class_id"
                            ],

                        "is_active":
                            bool(
                                row[
                                    "student_active"
                                ]
                            ),

                        "class": (
                            {
                                "id":
                                    row[
                                        "class_id"
                                    ],

                                "name":
                                    row[
                                        "class_name"
                                    ],

                                "section":
                                    row[
                                        "section"
                                    ],

                                "academic_year":
                                    row[
                                        "academic_year"
                                    ],
                            }
                            if row["class_id"]
                            is not None
                            else None
                        ),
                    },

                    "relationship":
                        row[
                            "relationship"
                        ],

                    "created_at":
                        row["created_at"],
                }
            )

        return {
            "success": True,
            "total": len(links),
            "data": links,
        }

    except Exception as e:
        print(
            "Admin parent links error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load "
                "parent links"
            ),
        )


# =========================================================
# GET SINGLE LINK
# =========================================================

@router.get(
    "/parent-links/{link_id}"
)
def get_parent_link(
    link_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                SELECT
                    id,
                    parent_user_id,
                    student_id,
                    relationship,
                    created_at

                FROM parent_students

                WHERE id = :link_id

                LIMIT 1
                """
            ),
            {
                "link_id": link_id,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Parent link not found"
                ),
            )

        return {
            "success": True,
            "data": {
                "id": row["id"],

                "parent_user_id":
                    row[
                        "parent_user_id"
                    ],

                "student_id":
                    row["student_id"],

                "relationship":
                    row[
                        "relationship"
                    ],

                "created_at":
                    row["created_at"],
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Parent link detail error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load "
                "parent link"
            ),
        )


# =========================================================
# CREATE LINK
# =========================================================

@router.post(
    "/parent-links",
    status_code=status.HTTP_201_CREATED,
)
def create_parent_link(
    payload: AdminParentLinkCreate,
    db: Session = Depends(get_db),
):
    try:
        # ---------------------------------
        # Parent profile exists
        # ---------------------------------

        parent = db.execute(
            text(
                """
                SELECT user_id
                FROM parent_profiles
                WHERE user_id =
                    :parent_user_id
                LIMIT 1
                """
            ),
            {
                "parent_user_id":
                    payload.parent_user_id,
            },
        ).first()

        if not parent:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Parent profile "
                    "not found"
                ),
            )

        # ---------------------------------
        # Student exists
        # ---------------------------------

        student = db.execute(
            text(
                """
                SELECT id
                FROM students
                WHERE id = :student_id
                LIMIT 1
                """
            ),
            {
                "student_id":
                    payload.student_id,
            },
        ).first()

        if not student:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )

        # ---------------------------------
        # Duplicate link
        # ---------------------------------

        duplicate = db.execute(
            text(
                """
                SELECT id

                FROM parent_students

                WHERE parent_user_id =
                    :parent_user_id

                AND student_id =
                    :student_id

                LIMIT 1
                """
            ),
            {
                "parent_user_id":
                    payload.parent_user_id,

                "student_id":
                    payload.student_id,
            },
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This parent is "
                    "already linked to "
                    "this student"
                ),
            )

        relationship = (
            payload.relationship.strip()
            if payload.relationship
            else None
        )

        result = db.execute(
            text(
                """
                INSERT INTO parent_students
                (
                    parent_user_id,
                    student_id,
                    relationship
                )

                VALUES
                (
                    :parent_user_id,
                    :student_id,
                    :relationship
                )
                """
            ),
            {
                "parent_user_id":
                    payload.parent_user_id,

                "student_id":
                    payload.student_id,

                "relationship":
                    relationship,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Parent linked to "
                "student successfully"
            ),
            "data": {
                "id":
                    result.lastrowid,

                "parent_user_id":
                    payload.parent_user_id,

                "student_id":
                    payload.student_id,

                "relationship":
                    relationship,
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Create parent link error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create "
                "parent link"
            ),
        )


# =========================================================
# UPDATE LINK
# =========================================================

@router.put(
    "/parent-links/{link_id}"
)
def update_parent_link(
    link_id: int,
    payload: AdminParentLinkUpdate,
    db: Session = Depends(get_db),
):
    try:
        # Existing link
        existing = db.execute(
            text(
                """
                SELECT id
                FROM parent_students
                WHERE id = :link_id
                LIMIT 1
                """
            ),
            {
                "link_id": link_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Parent link not found"
                ),
            )

        # Parent exists
        parent = db.execute(
            text(
                """
                SELECT user_id
                FROM parent_profiles
                WHERE user_id =
                    :parent_user_id
                LIMIT 1
                """
            ),
            {
                "parent_user_id":
                    payload.parent_user_id,
            },
        ).first()

        if not parent:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Parent profile "
                    "not found"
                ),
            )

        # Student exists
        student = db.execute(
            text(
                """
                SELECT id
                FROM students
                WHERE id = :student_id
                LIMIT 1
                """
            ),
            {
                "student_id":
                    payload.student_id,
            },
        ).first()

        if not student:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )

        # Duplicate excluding current link
        duplicate = db.execute(
            text(
                """
                SELECT id

                FROM parent_students

                WHERE parent_user_id =
                    :parent_user_id

                AND student_id =
                    :student_id

                AND id != :link_id

                LIMIT 1
                """
            ),
            {
                "parent_user_id":
                    payload.parent_user_id,

                "student_id":
                    payload.student_id,

                "link_id":
                    link_id,
            },
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This parent is "
                    "already linked to "
                    "this student"
                ),
            )

        relationship = (
            payload.relationship.strip()
            if payload.relationship
            else None
        )

        db.execute(
            text(
                """
                UPDATE parent_students

                SET
                    parent_user_id =
                        :parent_user_id,

                    student_id =
                        :student_id,

                    relationship =
                        :relationship

                WHERE id = :link_id
                """
            ),
            {
                "parent_user_id":
                    payload.parent_user_id,

                "student_id":
                    payload.student_id,

                "relationship":
                    relationship,

                "link_id":
                    link_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Parent link updated "
                "successfully"
            ),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Update parent link error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update "
                "parent link"
            ),
        )


# =========================================================
# UNLINK PARENT
# =========================================================

@router.delete(
    "/parent-links/{link_id}"
)
def delete_parent_link(
    link_id: int,
    db: Session = Depends(get_db),
):
    try:
        existing = db.execute(
            text(
                """
                SELECT id
                FROM parent_students
                WHERE id = :link_id
                LIMIT 1
                """
            ),
            {
                "link_id": link_id,
            },
        ).first()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Parent link not found"
                ),
            )

        db.execute(
            text(
                """
                DELETE FROM parent_students
                WHERE id = :link_id
                """
            ),
            {
                "link_id":
                    link_id,
            },
        )

        db.commit()

        return {
            "success": True,
            "message": (
                "Parent unlinked "
                "successfully"
            ),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "Delete parent link error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to unlink "
                "parent"
            ),
        )