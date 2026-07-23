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

# ── 访问密码（两者都设置才启用登录验证）──────────────────────
AUTH_USER     = os.environ.get("AUTH_USER", "")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")

# ── 会话密钥（用于网页登录的 Cookie 签名）──────────────────────
# 未显式配置时，从密码与令牌派生一个稳定值，保证重启后登录不失效
SECRET_KEY = os.environ.get("SECRET_KEY", "") or (
    "kids-cal:" + AUTH_PASSWORD + ":" + os.environ.get("CALENDAR_TOKEN", "")
)

# ── iCal 订阅令牌（设置后开启 /calendar/<token>.ics 订阅源）──────
CALENDAR_TOKEN = os.environ.get("CALENDAR_TOKEN", "")

# ── 孩子+学科 对应老师映射 ───────────────────────────────────
SUBJECT_TEACHER_MAP = {
    "张诺然": {
        "数学": "王婷婷老师",
        "语文": "晁静老师（班主任）",
        "英语": "胡清月老师",
    },
    "徐若愚": {
        "数学": "李老师（班主任）",
        "语文": "詹老师",
        "英语": "黄老师",
    },
}
