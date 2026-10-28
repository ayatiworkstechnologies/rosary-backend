from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TeacherExamScheduleCreate(BaseModel):
    class_id: int = Field(gt=0)
    exam_id: int = Field(gt=0)
    subject: str = Field(min_length=1, max_length=100)
    exam_date: date
    start_time: time
    end_time: time
    room: str | None = Field(default=None, max_length=100)
    instructions: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class TeacherExamScheduleUpdate(BaseModel):
    exam_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = Field(default=None, max_length=100)
    instructions: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_times(self):
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("End time must be after start time")
        return self
