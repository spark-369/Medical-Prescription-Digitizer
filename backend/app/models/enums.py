"""Application-level enums (stored as strings in the database for portability)."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    STAFF = "staff"


class PrescriptionStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def active_states(cls) -> set["PrescriptionStatus"]:
        return {cls.UPLOADED, cls.QUEUED, cls.PROCESSING}
