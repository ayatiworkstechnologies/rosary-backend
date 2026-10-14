
from typing import Literal

from pydantic import BaseModel, Field, model_validator


NotificationTarget = Literal[
    "ALL_PARENTS",
    "CLASSES",
    "INDIVIDUAL_PARENT",
]


class AdminNotificationTarget(BaseModel):
    target_type: NotificationTarget

    class_ids: list[int] = Field(
        default_factory=list,
    )

    parent_user_id: int | None = None

    @model_validator(mode="after")
    def validate_target(self):
        if self.target_type == "ALL_PARENTS":
            if self.class_ids or self.parent_user_id is not None:
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

        elif self.target_type == "INDIVIDUAL_PARENT":
            if self.parent_user_id is None or self.parent_user_id <= 0:
                raise ValueError(
                    "A valid Parent User ID is required"
                )

            if self.class_ids:
                raise ValueError(
                    "Class IDs are not allowed for individual notifications"
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


class AdminNotificationPreviewResponse(BaseModel):
    target_type: NotificationTarget
    recipient_count: int


class AdminNotificationSendResponse(BaseModel):
    message: str
    recipient_count: int
    notifications_created: int
