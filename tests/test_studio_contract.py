import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis import analyze, report_text
from models import Course, Dataset, Schedule
from studio_contract import normalize_course, normalize_schedule

FIXTURES = Path(__file__).parent / "fixtures/studio"


def test_recorded_studio_responses_produce_expected_semester():
    courses = [Course.model_validate(normalize_course(json.loads(p.read_text()), p.stem))
               for p in sorted(FIXTURES.glob("sample_0[123]*.json"))]
    schedule = Schedule.model_validate(normalize_schedule(
        json.loads((FIXTURES / "sample_04_schedule.raw.json").read_text())))
    result = analyze(Dataset(provenance="Recorded Studio API test", courses=courses, schedule=schedule), 7)
    assert [c.course_name for c in courses] == ["IoT 기초", "통계학 입문", "Global English II"]
    assert len(result["events"]) == 9
    assert [(w["week"], w["weight_points"]) for w in result["weeks"] if w["risk"] == "Red"] == [(8, 85), (16, 95)]
    assert result["unknown_count"] == 1
    assert courses[2].events[-1].week is None
    assert all(e.due_date is None for c in courses for e in c.events)
    assert schedule.available_hours_per_week == 12
    assert schedule.course_names == [c.course_name for c in courses]
    report = report_text(result)
    assert "주간 학습 가능 시간: 12시간" in report
    assert "이번 주 시간 배분 제안:" in report
    assert schedule.evidence in report


def test_missing_values_are_not_fabricated_and_invalid_values_still_fail():
    raw = {"course_name": "Test", "notes": None, "events": [{"title": "TBD", "week": 0,
           "due_date": "", "weight": 0, "page": 0}]}
    course = Course.model_validate(normalize_course(raw, "test.pdf"))
    assert course.events[0].week is None
    assert course.events[0].weight == 0
    assert raw["events"][0]["week"] == 0  # Preserve original evidence.
    raw["events"][0]["weight"] = 120
    with pytest.raises(ValidationError):
        Course.model_validate(normalize_course(raw, "test.pdf"))


def test_draft_event_schema_contains_required_title():
    config = json.loads((Path(__file__).parents[1] / "agent_configs/syllabus.draft.json").read_text())
    schema = config["agentConfig"]["informationExtractConfiguration"]["schemas"][0]["json_schema"]["schema"]
    event_schema = schema["properties"]["events"]["items"]
    assert "title" in event_schema["properties"]
    assert set(event_schema["required"]) <= set(event_schema["properties"])
