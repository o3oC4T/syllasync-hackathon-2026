import json
from pathlib import Path
from datetime import date
import pytest
from pydantic import ValidationError
from analysis import analyze, risk_level
from models import Dataset
from studio import parse_output, StudioError, StudioClient


@pytest.fixture
def data():
    return Dataset.model_validate_json((Path(__file__).parents[1] / "data/demo.json").read_text())


def test_three_course_demo(data):
    r=analyze(data, 7)
    assert len(r["events"]) == 9
    assert [(w["week"],w["weight_points"]) for w in r["weeks"] if w["risk"]=="Red"] == [(8,85),(16,95)]
    assert r["weeks"][13]["risk"] == "Yellow"
    assert r["unknown_count"] == 1
    assert r["ranking"][0]["score"] == 22.5
    assert all(r["title"] != "읽기 과제" for r in r["ranking"])


@pytest.mark.parametrize("count,weight,expected",[(0,0,"Green"),(1,39.9,"Green"),(1,40,"Yellow"),(2,20,"Yellow"),(1,80,"Red"),(3,0,"Red")])
def test_risk_boundaries(count,weight,expected):
    assert risk_level(count,weight)==expected


def test_past_events_never_recommended(data):
    r=analyze(data,15)
    assert len(r["ranking"])==3
    assert all(x["week"]==16 for x in r["ranking"])


def test_unknown_weight_and_missing_schedule(data):
    data.schedule=None
    data.courses[0].events[0].weight=None
    r=analyze(data)
    assert all(x["suggested_hours"] is None for x in r["ranking"])
    assert any("비중 미정" in x for x in r["issues"])
    assert any("시간 충돌" in x for x in r["issues"])


def test_duplicate_does_not_inflate_risk(data):
    data.courses[0].events.append(data.courses[0].events[0].model_copy())
    r=analyze(data)
    assert len(r["events"])==9
    assert any("중복" in x for x in r["issues"])


def test_date_conversion_needs_explicit_anchor(data):
    e=data.courses[2].events[-1];e.due_date=date(2026,11,10)
    assert analyze(data)["unknown_count"]==1
    r=analyze(data,semester_start=date(2026,9,1))
    assert r["unknown_count"]==0
    assert [x for x in r["events"] if x["title"]=="읽기 과제"][0]["week"]==11


def test_invalid_weights_are_rejected(data):
    raw=data.model_dump();raw["courses"][0]["events"][0]["weight"]=120
    with pytest.raises(ValidationError): Dataset.model_validate(raw)


def test_response_uses_last_message():
    r={"output":[{"type":"message","content":[{"type":"output_text","text":"old"}]}, {"type":"message","content":[{"type":"output_text","text":'{"course_name":"IoT"}'}]}]}
    assert parse_output(r)=={"course_name":"IoT"}
    with pytest.raises(StudioError): parse_output({"output_text":"# 리포트만 있는 결과"})


def test_api_request_and_file_cleanup(monkeypatch):
    client=StudioClient("test-placeholder")
    calls=[]
    def request(method,path,**kwargs):
        calls.append((method,path,kwargs))
        if path=="/files": return {"id":"file-1"}
        if path=="/responses": return {"id":"job-1","status":"completed","output_text":'{"course_name":"IoT"}'}
        return {"deleted":True}
    monkeypatch.setattr(client,"request",request)
    assert client.run("test.pdf",b"dummy","agent-test","cfg-test")=={"course_name":"IoT"}
    assert calls[1][2]["json"]["config_id"]=="cfg-test"
    assert calls[-1][0:2]==("DELETE","/files/file-1")


def test_api_failure_is_visible_and_still_cleans_up(monkeypatch):
    client=StudioClient("test-placeholder")
    calls=[]
    def request(method,path,**kwargs):
        calls.append((method,path))
        if path=="/files": return {"id":"file-1"}
        if path=="/responses": return {"status":"failed"}
        return {"deleted":True}
    monkeypatch.setattr(client,"request",request)
    with pytest.raises(StudioError): client.run("x.pdf",b"dummy","agent-test")
    assert calls[-1]==("DELETE","/files/file-1")
