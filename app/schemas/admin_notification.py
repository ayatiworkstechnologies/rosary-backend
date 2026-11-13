
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


NotificationTarget = Literal[
    "ALL_PARENTS",
    "CLASSES",
    "STUDENTS",
    "INDIVIDUAL_PARENT",
]

NotificationCategory = Literal[
    "GENERAL",
    "CIRCULAR",
    "IMPORTANT",
    "FEE_REMINDER",
]


class AdminNotificationTarget(BaseModel):
    target_type: NotificationTarget

    class_ids: list[int] = Field(
        default_factory=list,
    )

    student_ids: list[int] = Field(
        default_factory=list,
    )

    parent_user_id: int | None = None

    @model_validator(mode="after")
    def validate_target(self):
        if self.target_type == "ALL_PARENTS":
            if (
                self.class_ids
                or self.student_ids
                or self.parent_user_id is not None
            ):
                raise ValueError(
                    "All Parents cannot include class IDs or parent ID"
                )

        elif self.target_type == "CLASSES":
            if not self.class_ids:
                raise ValueError(
                    "Select at least one class"
                )

            if self.parent_user_id is not None:
                raise ValueError(
                    "Parent ID is not allowed for class notifications"
                )

            if any(class_id <= 0 for class_id in self.class_ids):
                raise ValueError(
                    "Class IDs must be positive"
                )

            if self.student_ids:
                raise ValueError(
                    "Student IDs are not allowed for class notifications"
                )

        elif self.target_type == "STUDENTS":
            if not self.student_ids:
                raise ValueError("Select at least one student")
            if self.class_ids or self.parent_user_id is not None:
                raise ValueError(
                    "Student notifications cannot include class IDs or parent ID"
                )
            if any(student_id <= 0 for student_id in self.student_ids):
                raise ValueError("Student IDs must be positive")

        elif self.target_type == "INDIVIDUAL_PARENT":
            if self.parent_user_id is None or self.parent_user_id <= 0:
                raise ValueError(
                    "A valid Parent User ID is required"
                )

            if self.class_ids:
                raise ValueError(
                    "Class IDs are not allowed for individual notifications"
                )

            if self.student_ids:
                raise ValueError(
                    "Student IDs are not allowed for individual notifications"
                )

        return self


class AdminNotificationPreviewRequest(
    AdminNotificationTarget
):
    pass


class AdminNotificationSendRequest(
    AdminNotificationTarget
):
    title: str = Field(
        min_length=3,
        max_length=200,
    )

    message: str = Field(
        min_length=3,
        max_length=5000,
    )

    category: NotificationCategory = "GENERAL"
    send_in_app: bool = True
    send_email: bool = False
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=64)
    confirmed_email_recipient_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_delivery(self):
        if not self.send_in_app and not self.send_email:
            raise ValueError("Select at least one delivery channel")
        if self.send_email:
            if not self.idempotency_key:
                raise ValueError("Email delivery requires an idempotency key")
            if self.confirmed_email_recipient_count is None:
                raise ValueError(
                    "Email delivery requires a confirmed recipient count"
                )
        if self.category == "FEE_REMINDER" and self.target_type not in {
            "STUDENTS",
            "INDIVIDUAL_PARENT",
        }:
            raise ValueError(
                "Fee reminders must target selected students or one parent"
            )
        return self


class AdminNotificationPreviewResponse(BaseModel):
    target_type: NotificationTarget
    recipient_count: int
    email_recipient_count: int
    missing_email_count: int
    invalid_email_count: int
    unverified_email_count: int
    opted_out_count: int
    deduplicated_email_count: int
    suppressed_email_count: int
    verified_email_recipient_count: int
    operational_email_recipient_count: int
    operational_unverified_email_count: int
    test_filtered_count: int
    email_sending_enabled: bool
    provider_ready: bool
    fee_reminders_enabled: bool


class AdminNotificationSendResponse(BaseModel):
    message: str
    recipient_count: int
    notifications_created: int
    batch_id: int | None = None
    email_queued: int = 0
    status: str
    idempotent_replay: bool = False


class EmailSuppressionRequest(BaseModel):
    email: EmailStr
    reason: str = Field(min_length=3, max_length=100)


class EmailSuppressionRemoveRequest(BaseModel):
    email: EmailStr
