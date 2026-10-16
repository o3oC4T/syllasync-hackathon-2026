"""Adapt Studio extraction's empty fields and text lists to the app contract."""
from copy import deepcopy
import re


def text_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.splitlines() if part.strip()]
    return value


def normalize_course(raw: dict, filename: str) -> dict:
    result = deepcopy(raw)
    result["source_file"] = filename
    result["notes"] = text_list(result.get("notes"))
    for field in ("assessments", "events"):
        if result.get(field) is None:
            result[field] = []
    for assessment in result.get("assessments", []):
        if assessment.get("weight") == "":
            assessment["weight"] = None
    for event in result.get("events", []):
        for field in ("week", "due_date", "weight", "page"):
            if event.get(field) == "":
                event[field] = None
        # Studio's numeric extraction uses 0 when a numeric field is absent.
        # Week/page are one-based; zero is an absence marker, never a date.
        for field in ("week", "page"):
            if event.get(field) == 0:
                event[field] = None
        for field, default in (("submission", "미기재"), ("evidence", "")):
            if event.get(field) is None:
                event[field] = default
    return result


def normalize_schedule(raw: dict) -> dict:
    result = deepcopy(raw)
    names = result.get("course_names")
    result["course_names"] = ([p.strip() for p in re.split(r"[\n,]", names) if p.strip()]
                              if isinstance(names, str) else text_list(names))
    result["constraints"] = text_list(result.get("constraints"))
    if result.get("available_hours_per_week") == "":
        result["available_hours_per_week"] = None
    if result.get("evidence") is None:
        result["evidence"] = ""
    return result
