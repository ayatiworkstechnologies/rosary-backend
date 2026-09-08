from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.models.attendance import Attendance
from app.models.user import User
from app.models.school_class import SchoolClass
from app.models.student import Student
from app.models.teacher_class import TeacherClass
from app.models.homework import Homework
from app.models.exam import Exam
from app.models.student_result import StudentResult     
from app.models.exam_schedule import ExamSchedule
from app.models.circular import Circular
from app.models.school_event import SchoolEvent
import app.models
from app.database import (
    Base,
    engine,
)

from app.routes.auth import (
    router as auth_router,
)
from app.routes.teacher import (
    router as teacher_router,
)
from app.routes.parent import (
    router as parent_router,
)


Base.metadata.create_all(
    bind=engine
)


app = FastAPI(
    title="Rosary School Portal API",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(teacher_router)
app.include_router(
    parent_router
)


@app.get("/")
def root():
    return {
        "message":
            "Rosary School Portal API running"
    }