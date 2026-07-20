"""
calendar_writer.py —— 通过 osascript 将作业写入苹果「日历.app」。
每个事件自动添加截止前提醒（见 config.REMINDER_MINUTES）。
"""
import subprocess
from datetime import datetime, timedelta

import config


# ── 公开接口 ─────────────────────────────────────────────────────────────────

def ensure_calendar_exists():
    """若「孩子作业提醒」日历不存在则自动创建。"""
    name = _esc(config.CALENDAR_NAME)
    _run(f"""
tell application "Calendar"
    if not (exists calendar "{name}") then
        make new calendar with properties {{name:"{name}"}}
    end if
end tell
""")


def create_homework_event(hw: dict) -> str:
    """创建日历事件并返回事件 UID（失败时返回空字符串）。"""
    deadline_str = (hw.get("deadline") or "").strip()
    if not deadline_str:
        return ""

    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return ""

    end_time = deadline + timedelta(hours=1)

    subject  = hw.get("subject", "作业")
    child    = hw.get("child_name", "")
    content  = hw.get("content", "")[:30]
    title    = f"[{subject}] {child} — {content}"
    desc     = (
        f"科目：{hw.get('subject','')}\n"
        f"内容：{hw.get('content','')}\n"
        f"要求：{hw.get('requirements','')}"
    )

    cal   = _esc(config.CALENDAR_NAME)
    t_esc = _esc(title)
    d_esc = _esc(desc)

    # 构建 AppleScript 中的提醒语句
    alarm_lines = "\n".join(
        f'        make new display alarm of the_event with properties {{trigger interval:{-m}}}'
        for m in config.REMINDER_MINUTES
    )

    script = f"""
tell application "Calendar"
    tell calendar "{cal}"
        -- 构造开始时间
        set s to current date
        set year  of s to {deadline.year}
        set month of s to {deadline.month}
        set day   of s to {deadline.day}
        set hours of s to {deadline.hour}
        set minutes of s to {deadline.minute}
        set seconds of s to 0

        -- 构造结束时间
        set e to current date
        set year  of e to {end_time.year}
        set month of e to {end_time.month}
        set day   of e to {end_time.day}
        set hours of e to {end_time.hour}
        set minutes of e to {end_time.minute}
        set seconds of e to 0

        set the_event to make new event with properties {{summary:"{t_esc}", start date:s, end date:e, description:"{d_esc}"}}
{alarm_lines}
        return uid of the_event
    end tell
end tell
"""
    result = _run(script)
    return result.strip() if result else ""


# ── 内部工具 ─────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """转义 AppleScript 字符串中的特殊字符。"""
    return (
        text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
    )


def _run(script: str) -> str:
    """通过 stdin 将 AppleScript 传给 osascript，返回 stdout。"""
    try:
        proc = subprocess.run(
            ["osascript"],
            input=script,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            print(f"[calendar] AppleScript 错误: {proc.stderr.strip()}")
            return ""
        return proc.stdout
    except Exception as exc:
        print(f"[calendar] osascript 调用失败: {exc}")
        return ""
