from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).parent / "data"
TZ = ZoneInfo("Asia/Almaty")
mcp = FastMCP("campuspulse")

SYNONYMS = {
    "тихое": "silent",
    "тихий": "silent",
    "тихо": "silent",
    "quiet": "silent",
    "розетка": "power",
    "розетки": "power",
    "socket": "power",
    "sockets": "power",
    "кофе": "coffee",
    "кафе": "cafe",
    "wifi": "wifi",
    "вайфай": "wifi",
    "группа": "group",
    "групповой": "group",
    "group": "group",
}


def _read(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _now() -> datetime:
    return datetime.now(TZ)


def _due_at(item: dict, now: datetime) -> datetime:
    if "due_offset_days" in item:
        due_date = (now + timedelta(days=float(item["due_offset_days"]))).date()
        hh, mm = [int(value) for value in item.get("due_time", "23:59").split(":")]
        return datetime.combine(due_date, time(hh, mm)).replace(tzinfo=TZ)
    return datetime.fromisoformat(item["due"]).replace(tzinfo=TZ)


def _starts_at(event: dict, now: datetime) -> datetime:
    if "day_offset" in event:
        event_date = (now + timedelta(days=int(event["day_offset"]))).date()
    else:
        event_date = datetime.fromisoformat(event["date"]).date()
    hh, mm = [int(value) for value in event.get("start", "00:00").split(":")]
    return datetime.combine(event_date, time(hh, mm)).replace(tzinfo=TZ)


def _is_open(hours: str, now: datetime) -> bool:
    if "24/7" in hours:
        return True
    try:
        start_raw, end_raw = [part.strip() for part in hours.split("-", 1)]
        start = datetime.strptime(start_raw, "%H:%M").time()
        end = datetime.strptime(end_raw, "%H:%M").time()
    except ValueError:
        return False
    current = now.time()
    if end <= start:
        return current >= start or current <= end
    return start <= current <= end


def _normalize_feature(value: str) -> str:
    cleaned = value.strip().lower()
    return SYNONYMS.get(cleaned, cleaned)


@mcp.tool(description="List current-semester courses with instructor, schedule and assignment count.")
def list_courses() -> str:
    records = [
        {
            "code": course["code"],
            "title": course["title"],
            "instructor": course["instructor"],
            "schedule": course["schedule"],
            "assignments": len(course.get("assignments", [])),
        }
        for course in _read("courses.json")
    ]
    return json.dumps(
        {"source": "campuspulse://courses", "records": records},
        ensure_ascii=False,
    )


@mcp.tool(description="Return upcoming assignment deadlines within N days. Filter by course code, title or assignment title.")
def get_deadlines(course: str = "", days: int = 14) -> str:
    now = _now()
    horizon = now + timedelta(days=max(1, min(int(days), 120)))
    needle = course.strip().lower()
    records = []

    for course_item in _read("courses.json"):
        course_haystack = f"{course_item['code']} {course_item['title']}".lower()
        for item in course_item.get("assignments", []):
            item_haystack = f"{course_haystack} {item['title']}".lower()
            if needle and needle not in item_haystack:
                continue
            due = _due_at(item, now)
            if not (now <= due <= horizon):
                continue
            records.append(
                {
                    "course": course_item["code"],
                    "course_title": course_item["title"],
                    "title": item["title"],
                    "due": due.isoformat(),
                    "days_left": round((due - now).total_seconds() / 86400, 1),
                    "weight": item.get("weight"),
                    "status": item.get("status", "unknown"),
                }
            )

    records.sort(key=lambda item: item["due"])
    return json.dumps(
        {
            "source": "campuspulse://courses",
            "as_of": now.isoformat(),
            "records": records,
        },
        ensure_ascii=False,
    )


@mcp.tool(description="Search upcoming campus events by text or tag. Use for questions about events and things to do on campus.")
def search_events(query: str = "", days: int = 14) -> str:
    now = _now()
    horizon = now + timedelta(days=max(1, min(int(days), 60)))
    needle = query.strip().lower()
    records = []

    for event in _read("events.json"):
        starts = _starts_at(event, now)
        if not (now <= starts <= horizon):
            continue
        haystack = " ".join(
            [
                event["title"],
                event.get("description", ""),
                " ".join(event.get("tags", [])),
            ]
        ).lower()
        if needle and needle not in haystack:
            continue
        records.append(
            {
                **event,
                "starts_at": starts.isoformat(),
                "source": "campuspulse://events",
            }
        )

    records.sort(key=lambda item: item["starts_at"])
    return json.dumps(
        {
            "source": "campuspulse://events",
            "as_of": now.isoformat(),
            "records": records,
        },
        ensure_ascii=False,
    )


@mcp.tool(description="Find study locations. features is comma-separated, e.g. 'silent, power, coffee'. open_now checks published hours.")
def find_study_spot(features: str = "", open_now: bool = True) -> str:
    now = _now()
    wanted = [
        _normalize_feature(value)
        for value in features.split(",")
        if value.strip()
    ]
    records = []

    for place in _read("locations.json"):
        if place.get("category") not in {"study", "lab", "cafe"}:
            continue
        place_features = [feature.lower() for feature in place.get("features", [])]
        if wanted and not all(
            any(
                wanted_feature in feature or feature in wanted_feature
                for feature in place_features
            )
            for wanted_feature in wanted
        ):
            continue
        is_open = _is_open(place.get("hours", ""), now)
        if open_now and not is_open:
            continue
        records.append(
            {
                **place,
                "open_now": is_open,
                "checked_at": now.isoformat(),
                "source": "campuspulse://locations",
            }
        )

    return json.dumps(
        {
            "source": "campuspulse://locations",
            "as_of": now.isoformat(),
            "note": "open_now uses published demo hours, not live occupancy.",
            "records": records,
        },
        ensure_ascii=False,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
