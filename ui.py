"""Tabler components and visualizations for the Streamlit dashboard.

All document-derived text is escaped before HTML rendering. Vendor CSS is
scoped to .ss so the Bootstrap reset cannot alter Streamlit's native controls.
"""
import base64
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"
COLORS = ("mint", "blue", "violet", "amber", "rose", "cyan", "slate")


def e(value):
    return escape(str(value), quote=True)


@lru_cache(maxsize=32)
def icon(name):
    # Only call with application-owned names, never user input.
    svg = (ASSETS / "vendor/tabler-icons" / f"{name}.svg").read_text()
    return svg.replace('<svg ', '<svg aria-hidden="true" focusable="false" ', 1)


def render(markup):
    st.markdown(f'<div class="ss">{markup}</div>', unsafe_allow_html=True)


def styles():
    nav_css = ""
    for i, name in enumerate(("layout-dashboard", "file-text", "code"), 1):
        encoded = base64.b64encode(icon(name).replace('currentColor', '#43664d').encode()).decode()
        nav_css += f'[data-testid="stRadioGroup"]>div:nth-child({i}) label:before{{background-image:url("data:image/svg+xml;base64,{encoded}")}}'
    st.markdown("<style>" + (ASSETS / "vendor/tabler-scoped.min.css").read_text()
                + (ASSETS / "dashboard.css").read_text() + nav_css + "</style>", unsafe_allow_html=True)


def brand():
    render(f'<div class="ss-brand"><span class="ss-mark">{icon("layers-intersect")}</span>'
           '<div>SyllaSync<span>나의 학기 지도</span></div></div>')


def sidebar_label(label):
    render(f'<div class="ss-nav-label">{e(label)}</div>')


def header(week, mode):
    label = {"가상 샘플 데모": "샘플 워크스페이스", "Studio API 분석": "문서 워크스페이스",
             "결과 JSON 불러오기": "가져온 워크스페이스"}[mode]
    render(f'<div class="ss-topline"><span>{icon("layout-dashboard")} 나의 워크스페이스'
           f'<span class="ss-slash">/</span><b>학기 대시보드</b></span>'
           f'<span class="ss-workspace">{e(label)}</span></div>'
           '<div class="ss-page-heading"><div><div class="ss-kicker">A LITTLE CLARITY. A BETTER SEMESTER.</div>'
           '<h1>한 학기를, 한눈에<span class="ss-period">.</span></h1>'
           '<p>바쁜 주간을 먼저 발견하고, 오늘의 준비 순서를 정하세요.</p></div>'
           f'<div class="ss-current-week">{icon("calendar-week")}<span>지금 나의 학기<strong>{week:02d}<small>주차</small></strong></span></div></div>')


def section(title, description="", eyebrow=""):
    render(f'<div class="ss-section">{f"<div class=ss-kicker>{e(eyebrow)}</div>" if eyebrow else ""}'
           f'<h2>{e(title)}</h2>{f"<p>{e(description)}</p>" if description else ""}</div>')


def overview(result, courses, current_week):
    weeks = result["weeks"]
    risk_label = {"Red": "집중", "Yellow": "주의", "Green": "여유"}
    columns = f'grid-template-columns:150px repeat({len(weeks)}, minmax(32px,1fr))'
    parts = [f'<div class="card ss-calendar"><div class="card-header"><div><h3 class="card-title">학기 일정 한눈에 보기</h3>'
              '<div class="ss-subtitle">과목별 일정과 주차별 집중도를 함께 확인하세요</div></div>'
              f'<span class="badge ss-badge-mint">{len(weeks)} WEEKS</span></div>'
              '<div class="ss-calendar-scroll" tabindex="0" role="region" aria-label="과목별 학기 일정표">'
              f'<div class="ss-matrix" style="{columns}"><div class="ss-matrix-label ss-muted">과목 / 주차</div>']
    for w in weeks:
        parts.append(f'<div class="ss-week-label {"is-current" if w["week"] == current_week else ""}">{w["week"]:02d}</div>')
    for i, course in enumerate(courses):
        color = COLORS[i % len(COLORS)]
        parts.append(f'<div class="ss-matrix-label"><span class="ss-dot {color}"></span><span>{e(course.course_name)}</span></div>')
        for w in weeks:
            events = [r for r in w["events"] if r["course"] == course.course_name]
            tooltip = f'{course.course_name} · {w["week"]}주차 · ' + (", ".join(r["title"] for r in events) or "등록 일정 없음")
            parts.append(f'<div class="ss-matrix-cell {"is-current" if w["week"] == current_week else ""}">'
                         f'<span class="ss-event-dot {color if events else "no-event"}" title="{e(tooltip)}" aria-label="{e(tooltip)}">'
                         f'{len(events) if events else ""}</span></div>')
    parts.append('<div class="ss-matrix-label ss-load-label">일정 집중도</div>')
    for w in weeks:
        color = w["risk"].lower() if w["count"] else "quiet"
        label = risk_label[w["risk"]] if w["count"] else "일정 없음"
        height = 10 + min(54, w["weight_points"] * .5)
        parts.append(f'<div class="ss-load-cell {"is-current" if w["week"] == current_week else ""}" '
                     f'title="{w["week"]}주차 · {label} · {w["count"]}건 · 비중 합계 {w["weight_points"]:g}점">'
                     f'<span class="ss-load-bar {color}" style="height:{height}px"></span><span>{w["count"] or "·"}</span></div>')
    parts.append('</div></div><div class="ss-calendar-footer"><span><i class="ss-legend-dot red"></i>집중'
                 '<i class="ss-legend-dot yellow"></i>주의<i class="ss-legend-dot green"></i>일정 있음'
                 '<i class="ss-legend-dot quiet"></i>일정 없음</span>'
                 f'<span class="ss-muted">테두리 표시는 현재 {current_week}주차</span></div></div>')
    render("".join(parts))


def focus(result):
    upcoming = [w for w in result["weeks"] if w["count"] and w["week"] >= result["current_week"]]
    nearest = upcoming[0] if upcoming else None
    if nearest:
        distance = nearest["week"] - result["current_week"]
        when = "이번 주" if distance == 0 else f"{distance}주 뒤"
        rows = "".join(f'<div class="ss-focus-event"><span>{e(row["course"])}</span><b>{e(row["title"])}</b></div>' for row in nearest["events"][:3])
        render(f'<div class="card ss-focus-card"><div class="ss-focus-eyebrow">{icon("sparkles")} UPCOMING FOCUS</div>'
               f'<div class="ss-focus-heading"><h3>{nearest["week"]}주차를<br>준비할 시간</h3><span class="ss-focus-orbit">{icon("calendar-week")}</span></div>'
               f'<p>{when}, {nearest["count"]}개의 일정이 기다리고 있어요.</p>{rows}'
               '<div class="ss-focus-footer">준비 우선순위 탭에서 시간 배분 확인</div></div>')
    else:
        render(f'<div class="card ss-focus-card"><div class="ss-focus-eyebrow">{icon("circle-check")} UPCOMING FOCUS</div>'
               '<h3>다가오는 일정을<br>모두 확인했어요.</h3><p>새 공지가 있다면 일정에 반영해 주세요.</p></div>')


def week_table(selected):
    risk = selected["risk"].lower() if selected["count"] else "quiet"
    title = f'{selected["week"]}주차의 시험·과제'
    head = (f'<div class="card ss-event-table"><div class="card-header"><h3 class="card-title">{title}</h3>'
            f'<span class="badge ss-badge-{risk}">{selected["count"]}개 일정</span></div>')
    if not selected["events"]:
        render(head + f'<div class="ss-empty-inline">{icon("calendar-week")}<b>아직 등록된 일정이 없어요</b><p>미정 과제와 이후 공지도 확인해 주세요.</p></div></div>')
        return
    rows = []
    for r in selected["events"]:
        weight = f'{r["weight"]:g}%' if r["weight"] is not None else "미정"
        rows.append(f'<tr><td><span class="ss-table-course">{e(r["course"])}</span></td><td>{e(r["title"])}</td>'
                    f'<td><span class="badge ss-badge-neutral">{weight}</span></td><td class="ss-muted">{e(r["submission"] or "미정")}</td></tr>')
    render(head + '<div class="table-responsive"><table class="table table-vcenter"><thead><tr>'
           '<th>과목</th><th>일정</th><th>평가 비중</th><th>제출 방식</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></div>')


def priority_cards(ranking):
    if not ranking:
        return
    cols = st.columns(min(3, len(ranking)))
    for i, (column, row) in enumerate(zip(cols, ranking[:3])):
        with column:
            hours = f'{row["suggested_hours"]:g}<small>시간</small>' if row["suggested_hours"] is not None else '—'
            render(f'<div class="card ss-priority-card"><div class="ss-priority-top"><span class="ss-rank">0{i+1}</span>'
                   f'<span class="badge ss-badge-mint">{row["week"]}주차</span></div>'
                   f'<p>{e(row["course"])}</p><h3>{e(row["title"])}</h3><div class="ss-priority-meta">평가 비중 {row["weight"]:g}% · 추천 점수 {row["score"]:g}</div>'
                   f'<div class="ss-hours"><span>이번 주 시간 제안</span><b>{hours}</b></div></div>')


def evidence_event(event):
    week = f'{event.week}주차' if event.week else '주차 미정'
    weight = f'{event.weight:g}%' if event.weight is not None else '비중 미정'
    render(f'<div class="ss-evidence-row"><div class="ss-evidence-title"><b>{e(event.title)}</b>'
           f'<span class="badge ss-badge-neutral">{week}</span><span class="badge ss-badge-neutral">{weight}</span></div>'
           f'<blockquote>{e(event.evidence or "근거 문장을 확인해 주세요.")}</blockquote>'
           f'<div class="ss-source">{icon("file-search")} 근거 위치 · {event.page or "미상"}쪽</div></div>')


def workflow():
    steps = [
        ("file-text", "01", "문서 입력", "강의계획서 · 개인 일정표", "PDF · DOCX · 이미지"),
        ("sparkles", "02", "Studio Agent", "Parse → Extract", "과목 일정 · 시간 제약 구조화"),
        ("layers-intersect", "03", "검증과 계산", "주차 병합 · 집중도 · 우선순위", "Python 규칙 기반 분석"),
        ("layout-dashboard", "04", "나의 학기 계획", "타임라인 · 원문 근거 · 리포트", "수정하고 다시 계획하기"),
    ]
    cards = ''.join(f'<div class="card ss-flow-step"><div class="ss-flow-step-top"><span class="ss-icon-box">{icon(i)}</span><span>{n}</span></div>'
                    f'<h3>{e(t)}</h3><p>{e(d)}</p><small>{e(s)}</small></div>' for i,n,t,d,s in steps)
    render('<div class="ss-flow-grid">' + cards + '</div>'
           f'<div class="card ss-flow-detail"><span class="ss-icon-box">{icon("sparkles")}</span>'
           '<div><h3>Load Agent로 전략 설명 더하기</h3><p>병합 리포트 PDF → Parse → Classify → 분류별 Extract → 전략 설명</p></div></div>')


def empty(mode):
    render(f'<div class="card ss-empty-state"><span class="ss-icon-box">{icon("file-text")}</span>'
           '<div class="ss-kicker">YOUR SEMESTER STARTS HERE</div><h2>문서 속 일정을, 나의 계획으로.</h2>'
           '<p>강의계획서와 일정표를 준비하면 시험·과제의 준비 순서를 정할 수 있어요.</p>'
           '<div class="ss-empty-steps"><span><b>01</b> 문서 준비</span><span><b>02</b> 일정 구조화</span><span><b>03</b> 나의 학기 확인</span></div>'
           f'<small>{"Studio 연결 설정에서 API Key와 Agent ID를 입력해 주세요." if mode == "Studio API 분석" else "SyllaSync에서 내려받은 구조화 데이터 JSON을 불러와 주세요."}</small></div>')
