from flask import Flask, request, jsonify, render_template, Response
from datetime import datetime, timedelta
import hmac

import config
import db
import parser
import calendar_writer
import ics_feed

app = Flask(__name__)
db.init_db()


# ── 访问密码（仅当 AUTH_PASSWORD 配置时生效，不校验用户名）──────
@app.before_request
def _require_auth():
    if not config.AUTH_PASSWORD:
        return None
    if request.path == "/logout":
        return None
    # iCal 订阅源用路径中的令牌验证，免登录（供苹果日历访问）
    if request.path.startswith("/calendar/") and request.path.endswith(".ics"):
        return None
    auth = request.authorization
    if auth and hmac.compare_digest(auth.password or "", config.AUTH_PASSWORD):
        return None
    return Response(
        "需要登录", 401,
        {"WWW-Authenticate": 'Basic realm="Restricted"'},
    )


# ── 页面 ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template(
        "index.html",
        children=config.CHILDREN,
        has_api_key=bool(config.OPENAI_API_KEY),
        auth_enabled=bool(config.AUTH_PASSWORD),
    )


@app.route("/logout")
def logout():
    """退出登录：用无效凭据覆盖浏览器缓存的 Basic Auth，再返回首页。"""
    html = """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>退出登录</title></head>
<body style="font-family:sans-serif;text-align:center;padding-top:80px;color:#333">
<p>正在退出登录…</p>
<script>
  try {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/', false, 'logout', 'logout-' + Date.now());
    xhr.send();
  } catch (e) {}
  setTimeout(function () { location.href = '/'; }, 300);
</script>
</body>
</html>"""
    return Response(html, 200, {"Content-Type": "text/html; charset=utf-8"})


@app.route("/calendar/<token>.ics")
def calendar_feed(token):
    """iCal 订阅源：Mac 日历订阅此地址即可自动同步作业与提醒。"""
    if not config.CALENDAR_TOKEN or not hmac.compare_digest(token, config.CALENDAR_TOKEN):
        return Response("Not Found", 404)
    ics = ics_feed.build_ics(db.get_all_homework())
    return Response(
        ics, 200,
        {"Content-Type": "text/calendar; charset=utf-8"},
    )


# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/ocr", methods=["POST"])
def api_ocr():
    """接收上传的截图，返回 OCR 文字 + 解析出的作业列表。"""
    if "image" not in request.files:
        return jsonify({"error": "未收到图片文件"}), 400

    f = request.files["image"]
    mime = f.mimetype or "image/png"
    if not mime.startswith("image/"):
        return jsonify({"error": "仅支持图片格式（PNG/JPG/WEBP）"}), 400

    child_name = request.form.get("child_name") or config.CHILDREN[0]
    image_bytes = f.read()

    result = parser.parse_homework_from_image(image_bytes, child_name, mime)
    return jsonify(result)


@app.route("/api/parse", methods=["POST"])
def api_parse():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    child_name = data.get("child_name") or config.CHILDREN[0]

    if not text:
        return jsonify({"error": "请粘贴钉钉消息内容"}), 400

    homeworks = parser.parse_homework(text, child_name)
    return jsonify({"homeworks": homeworks, "source_text": text})


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or {}
    homeworks = data.get("homeworks") or []
    source_text = data.get("source_text", "")
    create_cal = data.get("create_calendar", True)

    print(f"[保存] 收到 {len(homeworks)} 条作业，创建日历: {create_cal}")

    if create_cal:
        try:
            calendar_writer.ensure_calendar_exists()
            print("[保存] 日历已确保存在")
        except Exception as e:
            print(f"[保存] 日历创建失败: {e}")

    saved_ids = []
    duplicate_count = 0
    
    for i, hw in enumerate(homeworks):
        print(f"[保存] 处理作业 {i+1}: {hw.get('child_name')} - {hw.get('subject')}")
        hw["source_text"] = source_text
        
        # 处理循环模式
        pattern = (hw.get("recurrence_pattern") or "").strip()
        if pattern:
            # 循环模式存在，则生成多条作业
            expanded_hws = _expand_recurring_homework(hw, pattern)
            print(f"[保存] 循环模式 '{pattern}' 扩展为 {len(expanded_hws)} 条作业")
            
            for expanded_hw in expanded_hws:
                expanded_hw["source_text"] = source_text
                if db.homework_exists(expanded_hw):
                    duplicate_count += 1
                    print(f"[保存]   跳过重复作业: {expanded_hw.get('deadline')}")
                    continue
                if create_cal:
                    uid = calendar_writer.create_homework_event(expanded_hw)
                    expanded_hw["calendar_event_uid"] = uid
                    print(f"[保存]   日历事件 UID: {uid if uid else '创建失败'}")
                try:
                    db_id = db.insert_homework(expanded_hw)
                    saved_ids.append(db_id)
                    print(f"[保存]   数据库保存成功，ID: {db_id}")
                except Exception as e:
                    print(f"[保存]   数据库保存失败: {e}")
        else:
            # 无循环模式，直接保存
            if db.homework_exists(hw):
                duplicate_count += 1
                print(f"[保存] 跳过重复作业: {hw.get('deadline')}")
                continue
            if create_cal:
                uid = calendar_writer.create_homework_event(hw)
                hw["calendar_event_uid"] = uid
                print(f"[保存] 日历事件 UID: {uid if uid else '创建失败'}")
            try:
                db_id = db.insert_homework(hw)
                saved_ids.append(db_id)
                print(f"[保存] 数据库保存成功，ID: {db_id}")
            except Exception as e:
                print(f"[保存] 数据库保存失败: {e}")

    print(f"[保存] 完成，保存 {len(saved_ids)} 条，跳过重复 {duplicate_count} 条")
    return jsonify({"saved": len(saved_ids), "duplicates": duplicate_count, "ids": saved_ids})


def _expand_recurring_homework(hw: dict, pattern: str) -> list:
    """
    根据循环模式扩展作业。
    pattern: 逗号分隔的周日期，如 "1,3,5"（周一、周三、周五）
    返回本月从今天起所有匹配日期的作业副本
    """
    if not pattern.strip():
        return [hw]
    
    days = []
    try:
        days = [int(d.strip()) for d in pattern.split(',') if d.strip()]
    except ValueError:
        print(f"[expand] 循环模式格式错误: {pattern}")
        return [hw]
    
    if not days:
        return [hw]
    
    expanded = []
    today = datetime.now().date()
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    month_end = next_month - timedelta(days=1)

    check_date = today
    while check_date <= month_end:
        weekday = check_date.weekday()  # 0=周一, 6=周日

        # 转换为作业中的 weekday 格式（0=周日, 1=周一, ..., 6=周六）
        app_weekday = (weekday + 1) % 7

        if app_weekday in days:
            hw_copy = hw.copy()
            hw_copy["deadline"] = check_date.strftime("%Y-%m-%d 10:00")
            hw_copy["recurrence_pattern"] = ""
            expanded.append(hw_copy)

        check_date += timedelta(days=1)
    
    return expanded


@app.route("/api/homework", methods=["GET"])
def api_list():
    return jsonify({"homeworks": db.get_all_homework()})


@app.route("/api/homework/<int:hw_id>/status", methods=["POST"])
def api_update_status(hw_id):
    data = request.get_json(silent=True) or {}
    field = data.get("field", "")
    value = data.get("value", "")
    try:
        db.update_status(hw_id, field, value)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})


@app.route("/api/homework/<int:hw_id>/edit", methods=["POST"])
def api_edit(hw_id):
    """编辑作业的科目、内容、要求、截止时间。"""
    data = request.get_json(silent=True) or {}
    updates = {
        "subject": data.get("subject", ""),
        "teacher": data.get("teacher", ""),
        "publish_time": data.get("publish_time", ""),
        "content": data.get("content", ""),
        "requirements": data.get("requirements", ""),
        "deadline": data.get("deadline", ""),
    }
    db.update_homework(hw_id, updates)
    return jsonify({"ok": True})


@app.route("/api/homework/<int:hw_id>", methods=["DELETE"])
def api_delete(hw_id):
    db.delete_homework(hw_id)
    return jsonify({"ok": True})


@app.route("/api/homework/batch-delete", methods=["POST"])
def api_batch_delete():
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("ids") or []
    if not isinstance(raw_ids, list):
        return jsonify({"error": "作业 ID 必须是列表"}), 400

    homework_ids = sorted({item for item in raw_ids if isinstance(item, int) and item > 0})
    deleted_count = db.delete_homeworks(homework_ids)
    return jsonify({"ok": True, "deleted": deleted_count})


# ── 入口 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5001"))
    print(f"🚀  作业日历助手已启动 → http://{host}:{port}")
    app.run(debug=False, host=host, port=port)
