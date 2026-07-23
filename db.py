import sqlite3
import config


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS homework (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            child_name        TEXT    NOT NULL,
            subject           TEXT    DEFAULT '',
            teacher           TEXT    DEFAULT '',
            publish_time      TEXT    DEFAULT '',
            content           TEXT    DEFAULT '',
            requirements      TEXT    DEFAULT '',
            deadline          TEXT    DEFAULT '',
            recurrence_pattern TEXT   DEFAULT '',
            source_text       TEXT    DEFAULT '',
            submission_status TEXT    DEFAULT '未提交',
            review_status     TEXT    DEFAULT '未批改',
            correction_status TEXT    DEFAULT '无需订正',
            calendar_event_uid TEXT   DEFAULT '',
            created_at        TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)
    # 兼容旧表：缺失列时自动补充
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(homework)").fetchall()}
    for col in ("teacher", "publish_time"):
        if col not in existing:
            conn.execute(f"ALTER TABLE homework ADD COLUMN {col} TEXT DEFAULT ''")
    conn.commit()
    conn.close()


def insert_homework(hw: dict) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO homework
           (child_name, subject, teacher, publish_time, content, requirements, deadline,
            recurrence_pattern, source_text, calendar_event_uid)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            hw.get("child_name", ""),
            hw.get("subject", ""),
            hw.get("teacher", ""),
            hw.get("publish_time", ""),
            hw.get("content", ""),
            hw.get("requirements", ""),
            hw.get("deadline", ""),
            hw.get("recurrence_pattern", ""),
            hw.get("source_text", ""),
            hw.get("calendar_event_uid", ""),
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def homework_exists(hw: dict) -> bool:
    conn = get_conn()
    row = conn.execute(
        """SELECT 1 FROM homework
           WHERE child_name = ? AND subject = ? AND content = ?
             AND requirements = ? AND deadline = ?
           LIMIT 1""",
        (
            hw.get("child_name", ""),
            hw.get("subject", ""),
            hw.get("content", ""),
            hw.get("requirements", ""),
            hw.get("deadline", ""),
        ),
    ).fetchone()
    conn.close()
    return row is not None


def get_all_homework() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM homework ORDER BY deadline ASC, created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_status(hw_id: int, field: str, value: str):
    allowed = {"submission_status", "review_status", "correction_status"}
    if field not in allowed:
        raise ValueError(f"不允许修改字段: {field}")
    conn = get_conn()
    conn.execute(f"UPDATE homework SET {field} = ? WHERE id = ?", (value, hw_id))
    conn.commit()
    conn.close()


def delete_homework(hw_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM homework WHERE id = ?", (hw_id,))
    conn.commit()
    conn.close()


def delete_homeworks(hw_ids: list[int]) -> int:
    if not hw_ids:
        return 0
    placeholders = ", ".join("?" for _ in hw_ids)
    conn = get_conn()
    cur = conn.execute(f"DELETE FROM homework WHERE id IN ({placeholders})", hw_ids)
    conn.commit()
    deleted_count = cur.rowcount
    conn.close()
    return deleted_count


def update_homework(hw_id: int, updates: dict):
    """更新作业的 subject/content/requirements/deadline/recurrence_pattern 等字段。"""
    allowed = {"subject", "teacher", "publish_time", "content", "requirements", "deadline", "recurrence_pattern"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [hw_id]
    conn = get_conn()
    conn.execute(f"UPDATE homework SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
