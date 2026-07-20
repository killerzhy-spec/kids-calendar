"""
parser.py —— 将钉钉群消息解析为结构化作业列表。
优先使用 OpenAI API；未配置 Key 时返回手动填写模板。
支持从截图（图片字节）直接提取作业。
"""
import base64
import json
import re
from datetime import datetime

import config


def parse_homework(text: str, child_name: str) -> list[dict]:
    """返回作业字典列表，每条包含 subject/content/requirements/deadline 等字段。"""
    if config.OPENAI_API_KEY:
        result = _parse_with_ai(text, child_name)
        if result:
            return result
    return _empty_template(text, child_name)


# ── AI 解析 ──────────────────────────────────────────────────────────────────

def _parse_with_ai(text: str, child_name: str) -> list[dict]:
    try:
        from openai import OpenAI
    except ImportError:
        return []

    client = OpenAI(
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
    )

    today = datetime.now().strftime("%Y-%m-%d")

    system_prompt = f"""你是一个小学生作业信息提取助手。今天是 {today}。
从钉钉群消息中识别并提取所有作业任务，以 JSON 数组形式返回，每条作业包含：
- subject    : 科目（语文/数学/英语/科学/体育/美术/音乐/道法/其他）
- content    : 作业内容（简洁描述，保留页码、题目范围等关键信息）
- requirements: 具体要求，如书写格式、注意事项（没有则为空字符串）
- deadline   : 截止时间，格式严格为 "YYYY-MM-DD HH:MM"；
               只提日期时默认时间为 08:00；
               "明天" 指 {today} 的次日；未提及则为空字符串

只输出 JSON 数组，不加任何解释。若消息中无作业信息，返回 []。"""

    user_msg = f"孩子：{child_name}\n\n消息内容：\n{text}"

    try:
        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            timeout=30,
        )
        raw = resp.choices[0].message.content.strip()
        # 容错：提取第一个 JSON 数组
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            homeworks = json.loads(match.group())
            for hw in homeworks:
                hw["child_name"] = child_name
                # 确保字段存在
                hw.setdefault("subject", "")
                hw.setdefault("content", "")
                hw.setdefault("requirements", "")
                hw.setdefault("deadline", "")
            return homeworks
    except Exception as e:
        print(f"[parser] AI 解析失败: {e}")

    return []


# ── 截图解析 ─────────────────────────────────────────────────────────────────

def parse_homework_from_image(image_bytes: bytes, child_name: str, mime: str = "image/png") -> dict:
    """
    从截图字节中提取作业信息。
    返回 {'homeworks': [...], 'ocr_text': '...', 'method': '...', 'error': '...'}
    """
    if config.OPENAI_API_KEY:
        return _parse_image_with_api(image_bytes, child_name, mime)
    # 无 API Key 时尝试本地 OCR
    text = _ocr_local(image_bytes)
    if text:
        homeworks = _empty_template(text, child_name)
        return {"homeworks": homeworks, "ocr_text": text, "method": "local_ocr", "error": ""}
    return {
        "homeworks": [],
        "ocr_text": "",
        "method": "failed",
        "error": "未配置 OpenAI API Key，且本地 OCR 不可用。请在 .env 中填写 OPENAI_API_KEY 或手动粘贴文字。",
    }


def _parse_image_with_api(image_bytes: bytes, child_name: str, mime: str) -> dict:
    """调用 GPT-4o Vision，一步从截图提取结构化作业。"""
    try:
        from openai import OpenAI
    except ImportError:
        return {"homeworks": [], "ocr_text": "", "method": "failed", "error": "openai 包未安装"}

    client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)
    today  = datetime.now().strftime("%Y-%m-%d")
    b64    = base64.b64encode(image_bytes).decode()

    prompt = f"""你是一个小学生作业信息提取助手。今天是 {today}。
这是一张钉钉群聊截图，请：
1. 识别截图中的全部文字（ocr_text）
2. 从中提取所有作业任务（homeworks 数组）

每条作业字段：
- subject     : 科目（语文/数学/英语/科学/体育/美术/音乐/道法/其他）
- content     : 作业内容（保留页码/题目范围等关键信息）
- requirements: 具体要求，如书写格式（没有则为空字符串）
- deadline    : 截止时间，格式 "YYYY-MM-DD HH:MM"；只有日期则默认 08:00；未提及则为空字符串

只输出如下 JSON，不加任何解释：
{{"ocr_text":"...","homeworks":[{{"subject":"","content":"","requirements":"","deadline":""}}]}}"""

    try:
        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"孩子：{child_name}\n{prompt}"},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime};base64,{b64}",
                        "detail": "high",
                    }},
                ],
            }],
            temperature=0.1,
            timeout=60,
        )
        raw   = resp.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
            for hw in result.get("homeworks", []):
                hw["child_name"] = child_name
                hw.setdefault("subject", "")
                hw.setdefault("content", "")
                hw.setdefault("requirements", "")
                hw.setdefault("deadline", "")
            return {
                "homeworks": result.get("homeworks", []),
                "ocr_text":  result.get("ocr_text", ""),
                "method":    "gpt_vision",
                "error":     "",
            }
    except Exception as exc:
        print(f"[parser] Vision API 失败: {exc}")
        return {"homeworks": [], "ocr_text": "", "method": "failed", "error": str(exc)}

    return {"homeworks": [], "ocr_text": "", "method": "failed", "error": "未知错误"}


def _ocr_local(image_bytes: bytes) -> str:
    """尝试用 macOS Vision 框架做本地 OCR（需要 pyobjc-framework-Vision）。"""
    try:
        import tempfile, os
        import Vision  # type: ignore
        from Foundation import NSURL  # type: ignore

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_bytes)
            tmp = f.name

        try:
            results: list[str] = []

            def handler(req, err):
                if err:
                    return
                for obs in req.results():
                    candidates = obs.topCandidates_(1)
                    if candidates:
                        results.append(candidates[0].string())

            req = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
            req.setRecognitionLanguages_(["zh-Hans", "zh-Hant", "en-US"])
            req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)

            url_obj = NSURL.fileURLWithPath_(tmp)
            handler_obj = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url_obj, {})
            handler_obj.performRequests_error_([req], None)
            return "\n".join(results)
        finally:
            os.unlink(tmp)
    except Exception as exc:
        print(f"[ocr] 本地 OCR 不可用: {exc}")
        return ""


# ── 降级模板 ─────────────────────────────────────────────────────────────────

def _empty_template(text: str, child_name: str) -> list[dict]:
    """未配置 API Key 或 AI 失败时，返回一条手动填写模板。"""
    return [
        {
            "child_name": child_name,
            "subject": "",
            "content": text[:300] if text else "",
            "requirements": "",
            "deadline": "",
        }
    ]
