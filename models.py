"""Document evidence contract shared by Studio, local analysis and the UI."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Assessment(Record):
    name: str
    weight: float | None = Field(default=None, ge=0, le=100)


class Event(Record):
    title: str
    kind: Literal["exam", "assignment", "project", "presentation", "other"] = "other"
    week: int | None = Field(default=None, ge=1, le=20)
    due_date: date | None = None
    weight: float | None = Field(default=None, ge=0, le=100)
    submission: str = "미기재"
    evidence: str = ""
    page: int | None = Field(default=None, ge=1)


class Course(Record):
    course_name: str = Field(min_length=1)
    source_file: str = ""
    assessments: list[Assessment] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Schedule(Record):
    course_names: list[str] = Field(default_factory=list)
    available_hours_per_week: float | None = Field(default=None, ge=0, le=168)
    constraints: list[str] = Field(default_factory=list)
    evidence: str = ""


class Dataset(Record):
    provenance: str
    courses: list[Course] = Field(min_length=1)
    schedule: Schedule | None = None
