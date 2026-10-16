"""SyllaSync: syllabus evidence → a semester plan. Run: streamlit run app.py"""
import html
import json
import math
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

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
st.set_page_config(page_title="SyllaSync · 나의 학기 지도", page_icon="📚", layout="wide")
st.markdown("""<style>
.block-container{padding-top:4rem;max-width:1400px} h1,h2,h3{letter-spacing:-.04em}
[data-testid="stMetric"]{background:#fff;border:1px solid #dfe9e3;border-radius:15px;padding:14px 20px}
[data-testid="stMetricLabel"]{color:#637c72}[data-testid="stMetricValue"]{color:#154f47}
.eyebrow{font-size:12px;letter-spacing:.18em;color:#087f75;font-weight:700}
.hero{display:flex;justify-content:space-between;align-items:center;gap:30px;margin:6px 0 22px}
.hero h1{font-size:44px;margin:0 0 8px;line-height:1.2}.hero p{color:#61776e;font-size:17px;margin:0}
.pill{background:#e1f2e6;color:#176348;border-radius:40px;padding:10px 18px;white-space:nowrap;font-size:14px}
.week-grid{display:grid;grid-template-columns:repeat(8,1fr);gap:10px;margin:16px 0 18px}
.week{background:#fff;border:1px solid #dfe9e3;border-radius:12px;padding:13px;min-height:100px}
.week strong{display:block;font-size:21px;margin:9px 0 4px}.week small{font-size:11px}
.red{background:#fdece9;border-color:#edb1a5;color:#973a30}.yellow{background:#fff3d8;border-color:#ead494;color:#78591e}
.green{background:#e8f3ed;color:#2a624b}.empty{color:#82938c}.current{outline:2px solid #087f75}
.note{font-size:12px;color:#6c8177}.panel{padding:22px;border:1px solid #dfe9e3;border-radius:16px;background:white;margin-bottom:12px}
@media(max-width:900px){.week-grid{grid-template-columns:repeat(4,1fr)}.hero{display:block}.hero h1{font-size:34px}.pill{display:inline-block;margin-top:16px}}
</style>""", unsafe_allow_html=True)


def get_client():
    return StudioClient(api_key)


with st.sidebar:
    st.markdown("## SyllaSync")
    st.caption("실라싱크 · 나의 학기 지도")
    st.divider()
    mode = st.radio("데이터 선택", ["가상 샘플 데모", "Studio API 분석", "결과 JSON 불러오기"])
    current_week = st.slider("지금은 몇 주차인가요?", 1, 20, 7)
    use_dates = st.checkbox("날짜를 학기 주차로 환산")
    semester_start = st.date_input("1주차 시작일", date(2026, 9, 1)) if use_dates else None
    st.caption("주차만 있는 일정에는 정확한 날짜를 임의로 붙이지 않습니다.")
    with st.expander("Studio 연결 설정", expanded=False):
        api_key = st.text_input("Upstage API Key", value=os.getenv("UPSTAGE_API_KEY", ""), type="password")
        syllabus_id = st.text_input("Syllabus Agent ID", value=os.getenv("SYLLABUS_AGENT_ID", ""))
        schedule_id = st.text_input("Schedule Agent ID", value=os.getenv("SCHEDULE_AGENT_ID", ""))
        load_id = st.text_input("Load Agent ID", value=os.getenv("LOAD_AGENT_ID", ""))
        st.caption("Config ID는 .env에서 설정합니다. API 모드에서 업로드한 문서는 Upstage로 전송됩니다.")
    st.divider()
    st.caption("강의계획서를 읽는 시간은 줄이고,\n준비할 시간은 먼저 확보하세요.")

st.markdown('<div class="eyebrow">FROM SYLLABUS TO STRATEGY</div><div class="hero"><div><h1>한 학기를, 한눈에.</h1><p>시험이 몰리는 주를 먼저 알고, 오늘의 준비 순서를 정하세요.</p></div><div class="pill">SyllaSync · 실라싱크</div></div>', unsafe_allow_html=True)

if mode == "가상 샘플 데모":
    st.info("가상 샘플 3과목으로 체험합니다. 수작업으로 구성한 예시 데이터이며, 실시간 AI 추출 결과가 아닙니다.")
    if st.button("가상 샘플로 학기 분석", type="primary"):
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
    st.markdown('<div class="panel"><h3>학기 계획, 이 순서로 시작하세요.</h3><p>01 강의계획서 준비　 →　 02 시험·과제 구조화　 →　 03 집중 주간 확인　 →　 04 준비 순서 결정</p><span class="note">샘플 버튼을 누르면 8주차·16주차 시험 집중과 마감 미정 과제를 함께 확인할 수 있습니다.</span></div>', unsafe_allow_html=True)
    st.stop()

data = Dataset.model_validate(st.session_state.dataset)
result = analyze(data, current_week, semester_start)
text = report_text(result)
active = [w for w in result["weeks"] if w["risk"] == "Red" and w["week"] >= current_week]
c1, c2, c3, c4 = st.columns(4)
c1.metric("분석한 과목", f"{len(data.courses)}개")
c2.metric("시험·과제 일정", f"{len(result['events'])}건")
c3.metric("앞으로 집중할 주간", f"{len(active)}주")
c4.metric("마감 확인 필요", f"{result['unknown_count']}건")
st.write("")
timeline, priority, evidence, edit, flow = st.tabs(["학기 타임라인", "준비 우선순위", "원문 근거", "일정 수정", "처리 흐름"])

with timeline:
    st.subheader("바쁜 주간을 미리 발견하세요")
    st.caption("Red 집중 · Yellow 주의 · Green 일정 있음 · 회색 확인된 일정 없음")
    cards = []
    for w in result["weeks"]:
        cls = w["risk"].lower() if w["count"] else "empty"
        cls += " current" if w["week"] == current_week else ""
        label = f"{w['count']}건" if w["count"] else "—"
        detail = f"비중 합계 {w['weight_points']:g}점" if w["count"] else "등록 일정 없음"
        cards.append(f'<div class="week {cls}"><small>{w["week"]:02d} WEEK</small><strong>{label}</strong><small>{detail}</small></div>')
    st.markdown('<div class="week-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)
    chosen = st.selectbox("자세히 볼 주차", range(1, len(result["weeks"]) + 1), index=min(7, len(result["weeks"])-1), format_func=lambda w: f"{w}주차")
    selected = result["weeks"][chosen - 1]
    if selected["events"]:
        st.dataframe(pd.DataFrame([{"과목": r["course"], "일정": r["title"], "평가 비중": f'{r["weight"]:g}%' if r["weight"] is not None else "미정", "제출 방식": r["submission"]} for r in selected["events"]]), hide_index=True, width="stretch")
    else:
        st.caption("확인된 일정이 없습니다. 미정 과제와 이후 공지도 확인해 주세요.")
    st.caption(result["limitation"])

with priority:
    st.subheader("오늘 시작할 준비 순서")
    st.caption(f"{current_week}주차 기준 · 평가 비중, 남은 주차, 같은 주 일정 수로 계산합니다.")
    if result["ranking"]:
        top = result["ranking"][0]
        st.success(f"먼저 준비해 보세요: {top['course']} · {top['title']} · {top['week']}주차 · {top['weight']:g}%")
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
    st.subheader("추천을 만든 원문 근거")
    for c in data.courses:
        with st.expander(c.course_name, expanded=True):
            st.caption(c.source_file)
            for e in c.events:
                st.markdown(f"**{e.title}** · {str(e.week)+'주차' if e.week else '주차 미정'} · {str(e.weight)+'%' if e.weight is not None else '비중 미정'}")
                st.write(e.evidence or "근거 문장을 확인해 주세요.")
                st.caption(f"근거 위치: {e.page or '미상'}쪽")
    st.subheader("확인할 정보")
    for issue in result["issues"]:
        st.warning(issue)

with edit:
    st.subheader("새 공지가 나오면, 일정을 바로 고치세요")
    st.caption("원문 또는 공지로 확인한 주차·평가 비중만 입력하세요. 수정하면 추천도 다시 계산됩니다.")
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
    st.subheader("문서에서 계획까지, 근거를 이어갑니다")
    st.markdown("**강의계획서 → Syllabus Agent: Parse → Extract → 과목 JSON**\n\n**개인 일정표 → Schedule Agent: Parse → Extract → 시간 제약 JSON**\n\n**Python 병합·검증 → 주차별 집중도·우선순위 → Streamlit 화면·PDF 리포트**\n\n**병합 리포트 PDF → Load Agent: Parse → Classify → 분류별 Extract → 전략 설명**")
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
d1, d2, d3 = st.columns(3)
d1.download_button("학기 리포트 PDF", data=text_pdf("SyllaSync 학기 전략", text), file_name="SyllaSync_리포트.pdf", mime="application/pdf", width="stretch")
d2.download_button("구조화 데이터 JSON", data=data.model_dump_json(indent=2), file_name="SyllaSync_데이터.json", mime="application/json", width="stretch")
d3.download_button("분석 결과 JSON", data=json.dumps(result, ensure_ascii=False, indent=2), file_name="SyllaSync_분석.json", mime="application/json", width="stretch")
st.caption("SyllaSync · 대학생의 시험·과제 준비를 돕는 문서 기반 학기 계획 도구")
