"""SyllaSync: syllabus evidence → a semester plan. Run: streamlit run app.py"""
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from analysis import analyze, report_text
from models import Course, Dataset, Schedule
from pdf_export import text_pdf
from studio import StudioClient, StudioError
import ui

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
st.set_page_config(page_title="SyllaSync · 나의 학기 지도", page_icon="🌿", layout="wide")
ui.styles()


def get_client():
    return StudioClient(api_key)


with st.sidebar:
    ui.brand()
    ui.sidebar_label("WORKSPACE")
    mode = st.radio("데이터 선택", ["가상 샘플 데모", "Studio API 분석", "결과 JSON 불러오기"])
    st.divider()
    ui.sidebar_label("MY SEMESTER")
    current_week = st.slider("지금은 몇 주차인가요?", 1, 20, 7)
    use_dates = st.checkbox("날짜를 학기 주차로 환산")
    semester_start = st.date_input("1주차 시작일", date(2026, 9, 1)) if use_dates else None
    st.caption("정확한 날짜가 있는 일정만 주차로 환산합니다.")
    with st.expander("Studio 연결 설정", expanded=False):
        api_key = st.text_input("Upstage API Key", value=os.getenv("UPSTAGE_API_KEY", ""), type="password")
        syllabus_id = st.text_input("Syllabus Agent ID", value=os.getenv("SYLLABUS_AGENT_ID", ""))
        schedule_id = st.text_input("Schedule Agent ID", value=os.getenv("SCHEDULE_AGENT_ID", ""))
        load_id = st.text_input("Load Agent ID", value=os.getenv("LOAD_AGENT_ID", ""))
        st.caption("Config ID는 .env에서 설정합니다. API 모드에서 업로드한 문서는 Upstage로 전송됩니다.")
    connection_label = "연결 정보 입력됨 · 실행 시 검증" if api_key and syllabus_id else "Upstage 연결 설정 필요"
    ui.render(f'<div class="ss-connection">{ui.icon("plug-connected")}{connection_label}</div>')
    st.divider()
    ui.render('<div class="ss-team"><span class="avatar">S</span><div>std::~bug()<small>SyllaSync · 팀 워크스페이스</small></div></div>')

ui.header(current_week, mode)

if mode == "가상 샘플 데모":
    with st.container(key="demo_controls"):
        demo_note, demo_reset = st.columns([4, 1.25], vertical_alignment="center")
        with demo_note:
            ui.render('<div class="ss-demo-note"><span class="badge">DEMO</span><span>가상 샘플 데이터로 둘러보는 학기 대시보드</span></div>')
        reset_demo = demo_reset.button("가상 샘플로 학기 분석", width="stretch")
    if reset_demo or "dataset" not in st.session_state or st.session_state.get("dataset_mode") != mode:
        st.session_state.dataset = json.loads((ROOT / "data/demo.json").read_text(encoding="utf-8"))
        st.session_state.dataset_mode = mode
        st.session_state.pop("load_result", None)
        st.session_state.editor_version = st.session_state.get("editor_version", 0) + 1
elif mode == "결과 JSON 불러오기":
    uploaded_json = st.file_uploader("SyllaSync 구조화 데이터 JSON", type=["json"])
    if st.button("JSON으로 학기 분석", type="primary", disabled=uploaded_json is None):
        try:
            data = Dataset.model_validate_json(uploaded_json.getvalue())
            st.session_state.dataset = data.model_dump(mode="json")
            st.session_state.dataset_mode = mode
            st.session_state.pop("load_result", None)
            st.session_state.editor_version = st.session_state.get("editor_version", 0) + 1
        except (ValidationError, ValueError):
            st.error("SyllaSync 데이터 형식과 맞지 않습니다. data/demo.json을 확인하세요. 실행 리포트만 담긴 JSON은 입력할 수 없습니다.")
else:
    left, right = st.columns([2, 1])
    files = left.file_uploader("강의계획서 · 최대 7개, 파일당 10MB", type=["pdf", "docx"], accept_multiple_files=True)
    schedule_file = right.file_uploader("개인 일정표", type=["pdf", "png", "jpg", "jpeg"])
    if st.button("Studio로 문서 분석", type="primary"):
        if not files or len(files) > 7:
            st.error("강의계획서를 1~7개 올려 주세요.")
        elif not api_key or not syllabus_id or (schedule_file and not schedule_id):
            st.error("왼쪽 Studio 연결 설정에서 API Key와 사용할 Agent ID를 입력해 주세요.")
        else:
            try:
                client = get_client()
                courses = []
                with st.status("Studio에서 문서를 분석하고 있습니다.", expanded=True) as status:
                    for file in files:
                        st.write("강의계획서 분석: " + file.name)
                        raw = client.run(file.name, file.getvalue(), syllabus_id, os.getenv("SYLLABUS_CONFIG_ID", ""))
                        raw["source_file"] = file.name
                        courses.append(Course.model_validate(raw))
                    schedule = None
                    if schedule_file:
                        st.write("개인 일정표 분석 중")
                        schedule = Schedule.model_validate(client.run(schedule_file.name, schedule_file.getvalue(), schedule_id, os.getenv("SCHEDULE_CONFIG_ID", "")))
                    data = Dataset(provenance="Upstage Studio API 실행 결과 · 원문 대조 필요", courses=courses, schedule=schedule)
                    st.session_state.dataset = data.model_dump(mode="json")
                    st.session_state.dataset_mode = mode
                    st.session_state.pop("load_result", None)
                    st.session_state.editor_version = st.session_state.get("editor_version", 0) + 1
                    status.update(label="문서 분석 완료", state="complete")
                for warning in client.cleanup_warnings:
                    st.warning(warning)
            except (StudioError, ValidationError, ValueError) as exc:
                st.error(str(exc) if isinstance(exc, StudioError) else "Studio 출력이 스키마와 맞지 않습니다. Agent 설정과 결과 JSON을 확인해 주세요.")

if "dataset" not in st.session_state or st.session_state.get("dataset_mode") != mode:
    ui.empty(mode)
    st.stop()

data = Dataset.model_validate(st.session_state.dataset)
result = analyze(data, current_week, semester_start)
text = report_text(result)
active = [w for w in result["weeks"] if w["risk"] == "Red" and w["week"] >= current_week]
with st.container(key="metrics"):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("분석한 과목", f"{len(data.courses)}개", delta="나의 강의계획서", delta_color="off")
    c2.metric("시험·과제 일정", f"{len(result['events'])}건", delta="한곳에 모인 학기 일정", delta_color="off")
    c3.metric("앞으로 집중할 주간", f"{len(active)}주", delta="미리 준비할 집중 주간", delta_color="off")
    c4.metric("마감 확인 필요", f"{result['unknown_count']}건", delta="새 공지 확인하기", delta_color="off")
timeline, priority, evidence, edit, flow = st.tabs(["학기 타임라인", "준비 우선순위", "원문 근거", "일정 수정", "처리 흐름"])

with timeline:
    ui.section("학기의 흐름을 읽어보세요", "일정이 겹치는 주간을 발견하면, 준비할 시간이 생깁니다.")
    calendar, focus = st.columns([2.9, 1], gap="medium")
    with calendar:
        ui.overview(result, data.courses, current_week)
    with focus:
        ui.focus(result)
    week_control, week_hint = st.columns([1, 3], vertical_alignment="bottom")
    chosen = week_control.selectbox("자세히 볼 주차", range(1, len(result["weeks"]) + 1), index=min(7, len(result["weeks"])-1), format_func=lambda w: f"{w}주차")
    week_hint.caption("집중도는 일정 수와 평가 비중을 함께 반영합니다. 같은 주 일정이 실제 시간 충돌을 의미하지는 않습니다.")
    ui.week_table(result["weeks"][chosen - 1])
    st.caption(result["limitation"])

with priority:
    ui.section("오늘, 무엇부터 준비할까요?", f"{current_week}주차 기준 · 평가 비중, 남은 주차, 같은 주 일정 수로 정한 준비 순서입니다.")
    if result["ranking"]:
        ui.priority_cards(result["ranking"])
        ui.section("전체 준비 목록")
        table = []
        for i, r in enumerate(result["ranking"], 1):
            table.append({"순위": i, "과목": r["course"], "준비할 일": r["title"], "주차": r["week"], "평가 비중(%)": r["weight"], "추천 점수": r["score"], "이번 주 시간 제안": f'{r["suggested_hours"]:g}시간' if r["suggested_hours"] is not None else "가용 시간 미입력"})
        st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
    else:
        st.info("현재 주차 이후에 주차와 비중이 모두 확인된 일정이 없습니다.")
    st.caption("시간 제안은 입력된 주간 가용시간을 점수 비율로 나눈 값입니다. 실제 필요한 공부 시간을 예측한 결과는 아닙니다.")
    with st.expander("계산 기준 보기"):
        st.write(result["score_formula"])
        st.write(result["rules"])
        st.write("일정·비중 미정 항목과 지난 일정은 추천 점수 계산에서 제외합니다. 수치는 팀이 정한 설명 가능한 규칙이며, 학습 성과를 검증한 예측 모델은 아닙니다.")

with evidence:
    ui.section("모든 추천에는, 근거가 있어야 하니까.", "추출한 일정의 근거 문장과 출처 페이지를 확인하세요.")
    for c in data.courses:
        with st.expander(c.course_name, expanded=True):
            st.caption(c.source_file)
            for e in c.events:
                ui.evidence_event(e)
    ui.section("확인할 정보", "확정되지 않은 정보는 공지를 확인한 뒤 반영해 주세요.")
    for issue in result["issues"]:
        st.warning(issue)

with edit:
    ui.section("계획은 바뀌어도, 준비는 이어지도록.", "새 공지로 확인한 주차·평가 비중을 입력하세요. 수정하면 추천도 다시 계산됩니다.")
    edit_rows = [{"과목": c.course_name, "일정": e.title, "주차": e.week, "평가 비중(%)": e.weight} for c in data.courses for e in c.events]
    with st.form("edit_events"):
        edited = st.data_editor(pd.DataFrame(edit_rows), hide_index=True, disabled=["과목", "일정"],
            column_config={"주차": st.column_config.NumberColumn(min_value=1, max_value=20, step=1), "평가 비중(%)": st.column_config.NumberColumn(min_value=0, max_value=100, step=1)},
            key=f"event_editor_{st.session_state.get('editor_version', 0)}", width="stretch")
        hours_value = st.number_input("주간 학습 가능 시간", 0.0, 168.0, float(data.schedule.available_hours_per_week or 0) if data.schedule else 0.0, .5)
        has_hours = st.checkbox("입력한 시간을 추천에 반영", value=bool(data.schedule and data.schedule.available_hours_per_week is not None))
        submitted = st.form_submit_button("수정 반영하기", type="primary")
    if submitted:
        changed = data.model_dump(mode="json")
        i = 0
        for c in changed["courses"]:
            for e in c["events"]:
                r = edited.iloc[i]
                week = None if pd.isna(r["주차"]) else int(r["주차"])
                weight = None if pd.isna(r["평가 비중(%)"]) else float(r["평가 비중(%)"])
                if e["week"] != week or e["weight"] != weight:
                    e["evidence"] += " [주차 또는 비중: 사용자 수정값]"
                e.update(week=week, weight=weight)
                i += 1
        if not changed.get("schedule"):
            changed["schedule"] = {"course_names": [], "constraints": [], "evidence": "사용자 입력"}
        changed["schedule"]["available_hours_per_week"] = hours_value if has_hours else None
        try:
            st.session_state.dataset = Dataset.model_validate(changed).model_dump(mode="json")
            st.session_state.pop("load_result", None)
            st.rerun()
        except ValidationError:
            st.error("주차와 평가 비중의 입력 범위를 확인해 주세요.")

with flow:
    ui.section("문서에서 계획까지", "원문을 읽고, 근거를 모으고, 다음 행동으로 연결합니다.")
    ui.workflow()
    st.caption("데모에서는 미리 작성한 가상 JSON으로 병합 이후 단계를 실행합니다. Studio 연결은 실제 API 호출 시에만 사용합니다.")
    if st.button("Load Agent로 전략 설명 생성", disabled=not (api_key and load_id)):
        try:
            with st.spinner("Load Agent 실행 중"):
                client = get_client()
                st.session_state.load_result = client.run("SyllaSync_Load_Input.pdf", text_pdf("SyllaSync 병합 분석", text), load_id, os.getenv("LOAD_CONFIG_ID", ""))
                st.session_state.load_basis = text
            for warning in client.cleanup_warnings:
                st.warning(warning)
        except StudioError as exc:
            st.error(str(exc))
    if st.session_state.get("load_result") and st.session_state.get("load_basis") == text:
        st.json(st.session_state.load_result)
    st.caption("API Key와 Load Agent ID를 입력하면 실행할 수 있습니다. AI 설명은 위 규칙 기반 계산과 함께 확인하세요.")

st.divider()
ui.section("나의 계획, 어디서든 이어가기", "학기 리포트와 데이터를 내려받아 보관하세요.")
d1, d2, d3 = st.columns(3)
d1.download_button("학기 리포트 PDF", data=text_pdf("SyllaSync 학기 전략", text), file_name="SyllaSync_리포트.pdf", mime="application/pdf", width="stretch")
d2.download_button("구조화 데이터 JSON", data=data.model_dump_json(indent=2), file_name="SyllaSync_데이터.json", mime="application/json", width="stretch")
d3.download_button("분석 결과 JSON", data=json.dumps(result, ensure_ascii=False, indent=2), file_name="SyllaSync_분석.json", mime="application/json", width="stretch")
ui.render('<div class="ss-footer"><span><b>SyllaSync</b> · 조금 더 여유로운 학기를 위해</span><span>std::~bug() · 2026 Upstage Hackathon</span></div>')
