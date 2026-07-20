"""
ics_feed.py —— 将数据库中的作业生成 iCalendar (.ics) 订阅源。

Mac「日历.app」可通过「文件 → 新建日历订阅」订阅该源，
作业会自动同步并按 config.REMINDER_MINUTES 设置提醒。
时间按本地时间（浮动时间）处理，适合国内单一时区使用。
"""
from datetime import datetime, timedelta

import config


def _escape(text: str) -> str:
    """转义 iCalendar 文本字段中的特殊字符。"""
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """按 RFC 5545 将超过 75 字节的行折叠（续行以空格开头）。"""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    chunks = []
    start = 0
    limit = 75
    while start < len(raw):
        end = min(start + limit, len(raw))
        # 避免在 UTF-8 多字节字符中间截断
        while end > start and (raw[end - 1] & 0xC0) == 0x80 and end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1
        # 确保不在多字节序列中间断开
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end += 1
        chunks.append(raw[start:end].decode("utf-8"))
        start = end
        limit = 74  # 续行前置一个空格，可用长度少 1
    return "\r\n ".join(chunks)


def _fmt_local(dt: datetime) -> str:
    """浮动本地时间格式：20260721T100000"""
    return dt.strftime("%Y%m%dT%H%M%S")


def _fmt_utc(dt: datetime) -> str:
    """UTC 时间戳格式：20260721T020000Z"""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def build_ics(homeworks: list[dict]) -> str:
    """根据作业列表生成完整的 .ics 文本。"""
    now_stamp = _fmt_utc(datetime.utcnow())

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//kids-calendar//homework//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(config.CALENDAR_NAME)}",
        "X-WR-TIMEZONE:Asia/Shanghai",
        "X-PUBLISHED-TTL:PT30M",
    ]

    for hw in homeworks:
        deadline_str = (hw.get("deadline") or "").strip()
        if not deadline_str:
            continue
        try:
            start = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        end = start + timedelta(hours=1)

        subject = hw.get("subject", "") or "作业"
        child = hw.get("child_name", "")
        content = (hw.get("content", "") or "")[:40]
        summary = f"[{subject}] {child} — {content}".strip(" —")
        desc = (
            f"科目：{_escape(hw.get('subject',''))}\\n"
            f"内容：{_escape(hw.get('content',''))}\\n"
            f"要求：{_escape(hw.get('requirements',''))}"
        )
        uid = f"hw-{hw.get('id','')}@kids-calendar"

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        lines.append(f"DTSTAMP:{now_stamp}")
        lines.append(f"DTSTART:{_fmt_local(start)}")
        lines.append(f"DTEND:{_fmt_local(end)}")
        lines.append(_fold(f"SUMMARY:{_escape(summary)}"))
        lines.append(_fold(f"DESCRIPTION:{desc}"))

        for minutes in config.REMINDER_MINUTES:
            lines.append("BEGIN:VALARM")
            lines.append("ACTION:DISPLAY")
            lines.append(f"TRIGGER:-PT{int(minutes)}M")
            lines.append(_fold(f"DESCRIPTION:{_escape(summary)}"))
            lines.append("END:VALARM")

        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
