from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session

from app.database import get_db

from app.dependencies import (
    get_current_parent,
)

from app.models.user import User
from app.models.student import Student
from app.models.school_class import SchoolClass
from app.models.parent_student import ParentStudent

from app.schemas.parent import (
    ParentChildResponse,
    ParentChildrenListResponse,
)


router = APIRouter(
    prefix="/api/v1/parent",
    tags=["Parent"],
)


# =========================================================
# GET MY CHILDREN
# =========================================================

@router.get(
    "/children",
    response_model=ParentChildrenListResponse,
)
def get_my_children(
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    rows = (
        db.query(
            ParentStudent,
            Student,
            SchoolClass,
        )
        .join(
            Student,
            Student.id
            == ParentStudent.student_id,
        )
        .outerjoin(
            SchoolClass,
            SchoolClass.id
            == Student.class_id,
        )
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            Student.is_active.is_(True),
        )
        .order_by(
            Student.full_name.asc()
        )
        .all()
    )

    children = []

    for (
        parent_student,
        student,
        school_class,
    ) in rows:

        class_name = None
        academic_year = None

        if school_class:
            class_name = (
                f"{school_class.name} - "
                f"{school_class.section}"
            )

            academic_year = (
                school_class.academic_year
            )

        children.append(
            {
                "id":
                    student.id,

                "admission_no":
                    student.admission_no,

                "roll_no":
                    student.roll_no,

                "full_name":
                    student.full_name,

                "gender":
                    student.gender,

                "class_id":
                    student.class_id,

                "class_name":
                    class_name,

                "academic_year":
                    academic_year,

                "relationship":
                    parent_student.relationship,

                "status":
                    (
                        "Active"
                        if student.is_active
                        else "Inactive"
                    ),
            }
        )

    return {
        "total":
            len(children),

        "children":
            children,
    }


# =========================================================
# GET ONE CHILD
# =========================================================

@router.get(
    "/children/{student_id}",
    response_model=ParentChildResponse,
)
def get_my_child(
    student_id: int,
    db: Session = Depends(get_db),
    current_parent: User = Depends(
        get_current_parent
    ),
):
    row = (
        db.query(
            ParentStudent,
            Student,
            SchoolClass,
        )
        .join(
            Student,
            Student.id
            == ParentStudent.student_id,
        )
        .outerjoin(
            SchoolClass,
            SchoolClass.id
            == Student.class_id,
        )
        .filter(
            ParentStudent.parent_user_id
            == current_parent.id,

            ParentStudent.student_id
            == student_id,

            Student.is_active.is_(True),
        )
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    (
        parent_student,
        student,
        school_class,
    ) = row

    class_name = None
    academic_year = None

    if school_class:
        class_name = (
            f"{school_class.name} - "
            f"{school_class.section}"
        )

        academic_year = (
            school_class.academic_year
        )

    return {
        "id":
            student.id,

        "admission_no":
            student.admission_no,

        "roll_no":
            student.roll_no,

        "full_name":
            student.full_name,

        "gender":
            student.gender,

        "class_id":
            student.class_id,

        "class_name":
            class_name,

        "academic_year":
            academic_year,

        "relationship":
            parent_student.relationship,

        "status":
            (
                "Active"
                if student.is_active
                else "Inactive"
            ),
    }