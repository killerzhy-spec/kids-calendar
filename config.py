import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── OpenAI 配置 ──────────────────────────────────────────────
OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL    = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# ── 孩子名单 ─────────────────────────────────────────────────
CHILDREN = ["张诺然", "徐若愚"]

# ── 数据库 ───────────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "homework.db")

# ── 苹果日历名称 ─────────────────────────────────────────────
CALENDAR_NAME = "孩子作业提醒"

# ── 提前提醒时间（分钟），负数表示事件前 ──────────────────────
# 1440 = 提前1天，120 = 提前2小时
REMINDER_MINUTES = [1440, 120]
