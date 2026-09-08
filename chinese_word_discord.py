#!/usr/bin/env python3
"""Generate a beginner Chinese sentence with OpenAI and post it to Discord."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
DISCORD_CONFIG = BASE_DIR / "chinese_word_discord.env"
OPENAI_CONFIG = BASE_DIR / "chinese_word_discord_openai.env"
HISTORY_PATH = BASE_DIR / "chinese_word_discord_history.json"
TIMEZONE = ZoneInfo("Asia/Seoul")


def read_env_file(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        raise SystemExit(f"Missing config file: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {"weekly_themes": {}, "sentences": []}
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def save_history(history: dict) -> None:
    temporary = HISTORY_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, HISTORY_PATH)


def post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise SystemExit(f"HTTP {error.code}: {detail}") from error
    return json.loads(body) if body else {}


def generate_lesson(api_key: str, model: str, theme: str | None, used: list[str]) -> dict:
    fields = {
        "theme_chinese": {"type": "string"},
        "theme_pinyin": {"type": "string"},
        "theme_korean": {"type": "string"},
        "sentence_chinese": {"type": "string"},
        "sentence_pinyin": {"type": "string"},
        "sentence_korean_pronunciation": {"type": "string"},
        "sentence_korean_meaning": {"type": "string"},
    }
    schema = {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }
    theme_instruction = (
        f"이번 주 핵심 표현은 {theme}이다. 반드시 이 표현을 활용하라."
        if theme
        else "이번 주에 사용할 쉽고 실용적인 핵심 중국어 단어 또는 표현을 하나 새로 정하라."
    )
    prompt = f"""중국어와 한자를 전혀 모르는 한국인 초보자를 위한 오늘의 일상 문장 하나를 만든다.
{theme_instruction}
짧고 자연스러우며 실제 일상에서 쓸 수 있어야 한다. 병음에는 성조 기호를 표기하고 한글식 발음도 적는다.
아래 과거 중국어 문장과 완전히 동일한 문장은 절대 만들지 않는다:
{json.dumps(used, ensure_ascii=False)}"""
    response = post_json(
        "https://api.openai.com/v1/responses",
        {
            "model": model,
            "store": False,
            "input": [
                {"role": "developer", "content": "요청된 JSON 스키마를 정확히 따르고 설명은 추가하지 않는다."},
                {"role": "user", "content": prompt},
            ],
            "text": {"format": {"type": "json_schema", "name": "daily_chinese_lesson", "strict": True, "schema": schema}},
        },
        {"Authorization": f"Bearer {api_key}"},
    )
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return json.loads(content["text"])
    raise SystemExit("OpenAI response did not contain lesson text")


def format_message(lesson: dict) -> str:
    return (
        "🇨🇳 **오늘의 중국어**\n\n"
        f"**{lesson['sentence_chinese']}**\n"
        f"병음: {lesson['sentence_pinyin']}\n"
        f"읽기: {lesson['sentence_korean_pronunciation']}\n"
        f"뜻: {lesson['sentence_korean_meaning']}\n\n"
        f"핵심 표현: **{lesson['theme_chinese']}** "
        f"({lesson['theme_pinyin']}) — {lesson['theme_korean']}"
    )


def send_discord(webhook_url: str, message: str) -> None:
    parsed = urllib.parse.urlparse(webhook_url)
    if parsed.scheme != "https" or parsed.hostname not in {"discord.com", "discordapp.com"}:
        raise SystemExit("The configured value is not a valid Discord webhook URL")
    post_json(webhook_url, {"content": message}, {"User-Agent": "Chinese-Word-Discord/2.0"})


def main() -> None:
    discord_env = read_env_file(DISCORD_CONFIG)
    openai_env = read_env_file(OPENAI_CONFIG)
    webhook_url = discord_env.get("DISCORD_WEBHOOK_URL", "")
    api_key = openai_env.get("OPENAI_API_KEY", "")
    model = openai_env.get("OPENAI_MODEL", "gpt-5-mini")
    if not webhook_url:
        raise SystemExit("DISCORD_WEBHOOK_URL is not set")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set")

    now = datetime.now(TIMEZONE)
    date_key = now.date().isoformat()
    monday_key = (now.date() - timedelta(days=now.weekday())).isoformat()
    history = load_history()
    entries = history.setdefault("sentences", [])
    existing = next((entry for entry in entries if entry.get("date") == date_key), None)
    if existing and existing.get("sent"):
        return
    if existing:
        send_discord(webhook_url, existing["message"])
        existing["sent"] = True
        save_history(history)
        return

    themes = history.setdefault("weekly_themes", {})
    current_theme = themes.get(monday_key)
    theme_text = current_theme.get("chinese") if isinstance(current_theme, dict) else current_theme
    used = [entry.get("chinese", "") for entry in entries]
    lesson = generate_lesson(api_key, model, theme_text, used)
    if lesson["sentence_chinese"] in used:
        raise SystemExit("OpenAI generated a duplicate sentence; nothing was sent")

    themes.setdefault(monday_key, {
        "chinese": lesson["theme_chinese"],
        "pinyin": lesson["theme_pinyin"],
        "korean": lesson["theme_korean"],
    })
    message = format_message(lesson)
    entry = {
        "date": date_key,
        "week": monday_key,
        "theme": lesson["theme_chinese"],
        "chinese": lesson["sentence_chinese"],
        "message": message,
        "sent": False,
    }
    entries.append(entry)
    save_history(history)
    send_discord(webhook_url, message)
    entry["sent"] = True
    save_history(history)


if __name__ == "__main__":
    main()
