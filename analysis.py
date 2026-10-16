"""Transparent planning heuristics. Scores are not measured workload or collision claims."""
from collections import Counter
from datetime import date
from models import Dataset


def risk_level(count: int, weight: float) -> str:
    if count >= 3 or weight >= 80:
        return "Red"
    if count >= 2 or weight >= 40:
        return "Yellow"
    return "Green"


def analyze(data: Dataset, current_week: int = 7, semester_start: date | None = None) -> dict:
    if not 1 <= current_week <= 20:
        raise ValueError("현재 주차는 1~20으로 입력해 주세요.")
    rows, issues = [], []
    for course in data.courses:
        known = [x.weight for x in course.assessments if x.weight is not None]
        if course.assessments and (len(known) != len(course.assessments) or abs(sum(known) - 100) > .1):
            issues.append(f"{course.course_name}: 평가 비율 합계 또는 누락을 원문에서 확인하세요.")
        if not course.events:
            issues.append(f"{course.course_name}: 추출된 일정이 없습니다. 원문을 확인하세요.")
        seen = set()
        for event in course.events:
            week = event.week
            if event.due_date and semester_start:
                derived = (event.due_date - semester_start).days // 7 + 1
                if week is not None and week != derived:
                    issues.append(f"{course.course_name} / {event.title}: 날짜와 주차가 다릅니다. 원문 주차를 유지했습니다.")
                elif week is None and 1 <= derived <= 20:
                    week = derived
                elif week is None:
                    issues.append(f"{course.course_name} / {event.title}: 날짜가 설정한 20주 학기 범위 밖입니다.")
            key = (event.title, week, event.due_date)
            if key in seen:
                issues.append(f"{course.course_name} / {event.title}: 동일 일정 중복 1건을 제외했습니다.")
                continue
            seen.add(key)
            if week is None:
                issues.append(f"{course.course_name} / {event.title}: 주차 미정 · 공지 확인 필요")
            if event.weight is None:
                issues.append(f"{course.course_name} / {event.title}: 개별 평가 비중 미정 · 추천 점수 제외")
            if not event.evidence:
                issues.append(f"{course.course_name} / {event.title}: 근거 문장 확인 필요")
            rows.append({"course": course.course_name, "source_file": course.source_file,
                         **event.model_dump(mode="json"), "week": week})
    counts = Counter(r["week"] for r in rows if r["week"] is not None)
    weeks = []
    for week in range(1, max(16, max(counts, default=16)) + 1):
        items = [r for r in rows if r["week"] == week]
        weight = sum(r["weight"] or 0 for r in items)
        weeks.append({"week": week, "count": len(items), "weight_points": weight,
                      "risk": risk_level(len(items), weight), "events": items})
    ranking = []
    for row in rows:
        week, weight = row["week"], row["weight"]
        if week is None or week < current_week or weight is None:
            continue
        score = weight / (week - current_week + 1) * (1 + .25 * (counts[week] - 1))
        ranking.append({**row, "score": round(score, 2)})
    ranking.sort(key=lambda r: (-r["score"], r["week"], r["course"], r["title"]))
    hours = data.schedule.available_hours_per_week if data.schedule else None
    score_sum = sum(r["score"] for r in ranking)
    for row in ranking:
        row["suggested_hours"] = round(hours * row["score"] / score_sum, 1) if hours is not None and score_sum else None
    if data.schedule is None:
        issues.append("개인 일정표 미입력: 시간 충돌과 실제 학습 가능 시간은 판단하지 않습니다.")
    elif data.schedule.course_names:
        missing = set(data.schedule.course_names) - {c.course_name for c in data.courses}
        if missing:
            issues.append("시간표에 있으나 강의계획서가 없는 과목: " + ", ".join(sorted(missing)))
    courses = []
    for course in data.courses:
        items = [r for r in rows if r["course"] == course.course_name]
        levels = [risk_level(sum(r["week"] == w for r in items), sum(r["weight"] or 0 for r in items if r["week"] == w))
                  for w in {r["week"] for r in items if r["week"] is not None}]
        peak = max(levels, key=lambda x: {"Green": 0, "Yellow": 1, "Red": 2}[x], default="Green")
        courses.append({"course": course.course_name, "event_count": len(items), "peak_load": peak})
    return {"provenance": data.provenance, "current_week": current_week, "weeks": weeks,
            "available_hours_per_week": hours,
            "schedule_evidence": data.schedule.evidence if data.schedule else "",
            "events": rows, "ranking": ranking, "courses": courses,
            "issues": list(dict.fromkeys(issues)),
            "unknown_count": sum(r["week"] is None for r in rows),
            "rules": "Red: 주간 3건 이상 또는 비중 합계 80점 이상. Yellow: 2건 이상 또는 40점 이상. 그 외 Green.",
            "score_formula": "평가 비중 ÷ (남은 주차 + 1) × (1 + 0.25 × 같은 주 다른 일정 수)",
            "limitation": "비중 합계는 서로 다른 과목의 상대적 일정 부담 지표이며, 학점이나 실제 소요 시간을 뜻하지 않습니다. 같은 주 집중은 시간 충돌을 뜻하지 않습니다."}


def report_text(result: dict) -> str:
    lines = ["SyllaSync 학기 전략 리포트", "데이터: " + result["provenance"],
             f"분석 기준: {result['current_week']}주차"]
    hours = result.get("available_hours_per_week")
    lines += [f"주간 학습 가능 시간: {hours:g}시간" if hours is not None else "주간 학습 가능 시간: 미입력",
              "개인 일정 근거: " + (result.get("schedule_evidence") or "미기재"), "", "일정 집중 주간"]
    for week in result["weeks"]:
        if week["count"]:
            lines.append(f"{week['week']}주차 | {week['risk']} | {week['count']}건 | 평가 비중 합계 {week['weight_points']:g}점")
    lines += ["", "준비 우선순위"]
    for i, row in enumerate(result["ranking"], 1):
        lines.append(f"{i}. {row['course']} · {row['title']} · {row['week']}주차 · {row['weight']:g}% · 추천 점수 {row['score']}")
        if row.get("suggested_hours") is not None:
            lines.append(f"   이번 주 시간 배분 제안: {row['suggested_hours']:g}시간")
        lines.append(f"   근거: {row['evidence']} ({row['source_file']}, {row['page'] or '미상'}쪽)")
    lines += ["", "확인할 정보", *result["issues"], "", "산정 기준", result["rules"],
              result["score_formula"], result["limitation"],
              "학습 시간은 입력한 주간 가용시간을 추천 점수 비율로 배분한 제안이며, 필요한 공부 시간을 예측한 값이 아닙니다."]
    return "\n".join(lines)
