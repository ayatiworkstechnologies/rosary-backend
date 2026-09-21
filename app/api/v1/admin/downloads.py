from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session


from app.database import get_db
from app.models.download_form import DownloadForm
from app.models.school_class import SchoolClass
from app.schemas.admin_download import AdminDownloadResponse


router = APIRouter(
    prefix="/api/v1/admin/downloads",
    tags=["Admin Downloads"],
)


UPLOAD_DIR = Path("uploads/download_forms")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_AUDIENCES = {
    "ALL",
    "PARENT",
    "STUDENT",
    "TEACHER",
}


def validate_audience(audience: str) -> str:
    value = audience.strip().upper()

    if value not in ALLOWED_AUDIENCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Audience must be one of: "
                "ALL, PARENT, STUDENT, TEACHER"
            ),
        )

    return value


def validate_class(
    db: Session,
    class_id: int | None,
) -> None:
    if class_id is None:
        return

    school_class = (
        db.query(SchoolClass)
        .filter(SchoolClass.id == class_id)
        .first()
    )

    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )


async def save_uploaded_file(
    file: UploadFile,
) -> tuple[str, str]:
    original_name = file.filename or "document"

    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, DOC and DOCX files are allowed",
        )

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must not exceed 10 MB",
        )

    stored_name = f"{uuid4().hex}{extension}"

    file_path = UPLOAD_DIR / stored_name

    file_path.write_bytes(contents)

    file_url = (
        f"/uploads/download_forms/{stored_name}"
    )

    return original_name, file_url


def delete_uploaded_file(file_url: str | None) -> None:
    if not file_url:
        return

    filename = Path(file_url).name

    file_path = UPLOAD_DIR / filename

    if file_path.exists() and file_path.is_file():
        file_path.unlink()


# ---------------------------------------------------------
# GET ALL DOWNLOADS
# ---------------------------------------------------------

@router.get(
    "",
    response_model=list[AdminDownloadResponse],
)
def get_downloads(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    audience: str | None = Query(default=None),
    class_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(DownloadForm)

    if search:
        query = query.filter(
            DownloadForm.title.ilike(f"%{search}%")
        )

    if category:
        query = query.filter(
            DownloadForm.category == category
        )

    if audience:
        query = query.filter(
            DownloadForm.audience
            == audience.strip().upper()
        )

    if class_id is not None:
        query = query.filter(
            DownloadForm.class_id == class_id
        )

    if is_active is not None:
        query = query.filter(
            DownloadForm.is_active == is_active
        )

    return (
        query
        .order_by(
            DownloadForm.published_date.desc(),
            DownloadForm.id.desc(),
        )
        .all()
    )


# ---------------------------------------------------------
# GET ONE DOWNLOAD
# ---------------------------------------------------------

@router.get(
    "/{download_id}",
    response_model=AdminDownloadResponse,
)
def get_download(
    download_id: int,
    db: Session = Depends(get_db),
):
    download = (
        db.query(DownloadForm)
        .filter(DownloadForm.id == download_id)
        .first()
    )

    if not download:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download form not found",
        )

    return download


# ---------------------------------------------------------
# CREATE DOWNLOAD
# ---------------------------------------------------------

@router.post(
    "",
    response_model=AdminDownloadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_download(
    title: str = Form(...),
    category: str = Form(...),
    description: str | None = Form(None),
    audience: str = Form(...),
    class_id: int | None = Form(None),
    published_date: date = Form(...),
    is_active: bool = Form(True),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    title = title.strip()
    category = category.strip()

    if not title:
        raise HTTPException(
            status_code=422,
            detail="Title is required",
        )

    if not category:
        raise HTTPException(
            status_code=422,
            detail="Category is required",
        )

    audience = validate_audience(audience)

    validate_class(
        db=db,
        class_id=class_id,
    )

    file_name, file_url = await save_uploaded_file(
        file
    )

    download = DownloadForm(
        title=title,
        category=category,
        description=(
            description.strip()
            if description
            else None
        ),
        audience=audience,
        class_id=class_id,
        file_name=file_name,
        file_url=file_url,
        published_date=published_date,
        is_active=is_active,
    )

    try:
        db.add(download)
        db.commit()
        db.refresh(download)

    except Exception:
        db.rollback()

        delete_uploaded_file(file_url)

        raise

    return download


# ---------------------------------------------------------
# UPDATE DOWNLOAD
# ---------------------------------------------------------

@router.put(
    "/{download_id}",
    response_model=AdminDownloadResponse,
)
async def update_download(
    download_id: int,
    title: str | None = Form(None),
    category: str | None = Form(None),
    description: str | None = Form(None),
    audience: str | None = Form(None),
    class_id: int | None = Form(None),
    published_date: date | None = Form(None),
    is_active: bool | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    download = (
        db.query(DownloadForm)
        .filter(DownloadForm.id == download_id)
        .first()
    )

    if not download:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download form not found",
        )

    if title is not None:
        title = title.strip()

        if not title:
            raise HTTPException(
                status_code=422,
                detail="Title cannot be empty",
            )

        download.title = title

    if category is not None:
        category = category.strip()

        if not category:
            raise HTTPException(
                status_code=422,
                detail="Category cannot be empty",
            )

        download.category = category

    if description is not None:
        download.description = (
            description.strip()
            if description.strip()
            else None
        )

    if audience is not None:
        download.audience = validate_audience(
            audience
        )

    if class_id is not None:
        validate_class(
            db=db,
            class_id=class_id,
        )

        download.class_id = class_id

    if published_date is not None:
        download.published_date = published_date

    if is_active is not None:
        download.is_active = is_active

    old_file_url = None
    new_file_url = None

    if file is not None:
        old_file_url = download.file_url

        file_name, new_file_url = (
            await save_uploaded_file(file)
        )

        download.file_name = file_name
        download.file_url = new_file_url

    try:
        db.commit()
        db.refresh(download)

    except Exception:
        db.rollback()

        if new_file_url:
            delete_uploaded_file(new_file_url)

        raise

    if old_file_url:
        delete_uploaded_file(old_file_url)

    return download


# ---------------------------------------------------------
# ACTIVATE / DEACTIVATE
# ---------------------------------------------------------

@router.patch(
    "/{download_id}/status",
    response_model=AdminDownloadResponse,
)
def update_download_status(
    download_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
):
    download = (
        db.query(DownloadForm)
        .filter(DownloadForm.id == download_id)
        .first()
    )

    if not download:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download form not found",
        )

    download.is_active = is_active

    db.commit()
    db.refresh(download)

    return download


# ---------------------------------------------------------
# DELETE DOWNLOAD
# ---------------------------------------------------------

@router.delete(
    "/{download_id}",
)
def delete_download(
    download_id: int,
    db: Session = Depends(get_db),
):
    download = (
        db.query(DownloadForm)
        .filter(DownloadForm.id == download_id)
        .first()
    )

    if not download:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download form not found",
        )

    file_url = download.file_url

    db.delete(download)
    db.commit()

    delete_uploaded_file(file_url)

    return {
        "message": "Download form deleted successfully"
    }