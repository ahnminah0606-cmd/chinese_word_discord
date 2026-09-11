#!/usr/bin/env python3
"""Generate a progressive beginner Chinese mini-dialogue and post it to Discord."""

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
DISCORD_CONFIG = BASE_DIR / "chinese_word_discord.env"
OPENAI_CONFIG = BASE_DIR / "chinese_word_discord_openai.env"
HISTORY_PATH = BASE_DIR / "chinese_word_discord_history.json"
TIMEZONE = ZoneInfo("Asia/Seoul")
COURSE_START = date(2026, 9, 8)


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
        return {"course_start": COURSE_START.isoformat(), "weekly_conversations": {}, "dialogues": []}
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
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:1000]
            if error.code < 500 and error.code != 429:
                raise SystemExit(f"HTTP {error.code}: {detail}") from error
            last_error = f"HTTP {error.code}: {detail}"
        except (TimeoutError, socket.timeout, urllib.error.URLError) as error:
            last_error = str(error)
        if attempt < 2:
            time.sleep(10 * (attempt + 1))
    raise SystemExit(f"Request failed after 3 attempts: {last_error}")


def course_level(today: date) -> tuple[int, str]:
    week_number = max(0, (today - COURSE_START).days // 7)
    level = min(4, week_number // 4 + 1)
    descriptions = {
        1: "아기 단계: 두 사람이 한 번씩 말한다. 각 중국어 발화는 되도록 2~8자로 매우 짧게 쓴다.",
        2: "첫걸음 단계: 2번 주고받는다. 아주 쉬운 시간 또는 장소 표현을 하나까지 쓸 수 있다.",
        3: "쉬운 기초 단계: 2~3번 주고받는다. 날씨·약속·식사·쇼핑·이동·기분 같은 일상 주제에서 짧은 질문이나 대답을 쓴다.",
        4: "쉬운 생활 회화 단계: 2~3번만 주고받는다. 초보자가 바로 따라 말할 수 있는 짧은 일상 문장만 쓰고 각 발화는 되도록 15자를 넘기지 않는다.",
    }
    return level, descriptions[level]


def generate_dialogue(api_key: str, model: str, weekly: dict | None, used: list[str], level_text: str) -> dict:
    line_schema = {
        "type": "object",
        "properties": {
            "speaker": {"type": "string", "enum": ["A", "B"]},
            "chinese": {"type": "string"},
            "pinyin": {"type": "string"},
            "korean_pronunciation": {"type": "string"},
            "korean_meaning": {"type": "string"},
        },
        "required": ["speaker", "chinese", "pinyin", "korean_pronunciation", "korean_meaning"],
        "additionalProperties": False,
    }
    fields = {
        "weekly_chinese": {"type": "string"},
        "weekly_pinyin": {"type": "string"},
        "weekly_korean_pronunciation": {"type": "string"},
        "weekly_korean_meaning": {"type": "string"},
        "situation": {"type": "string"},
        "lines": {"type": "array", "items": line_schema, "minItems": 2, "maxItems": 3},
    }
    schema = {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}
    if weekly:
        weekly_rule = f"이번 주 핵심 회화는 반드시 '{weekly['chinese']}'이다. 대화 발화 중 하나에 이 문장을 그대로 사용한다."
    else:
        weekly_rule = "이번 주에 매일 반복할 아주 쉬운 완성형 핵심 회화 문장을 하나 정하고 대화 발화 중 하나에 그대로 사용한다."
    prompt = f"""중국어와 한자를 전혀 모르는 한국인 초보자의 하루치 미니 회화를 만든다.
난이도 규칙: {level_text}
{weekly_rule}
실제 일상에서 바로 쓸 수 있고 문법적으로 자연스러워야 한다. 병음에는 성조 기호를 넣고 한글식 발음은 한국인이 읽기 쉽게 쓴다.
과정이 몇 달 진행되어도 어려운 어휘, 성어, 문어체, 격식체, 긴 문장, 복잡한 문법과 여러 절이 연결된 문장을 쓰지 않는다. 최종 목표는 '날씨가 정말 좋네요', '오늘은 친구랑 놀러 갈 거예요' 정도의 아주 쉬운 일상 회화다.
같은 주의 핵심 회화 문장은 반복 학습을 위해 매일 다시 사용해도 된다. 하지만 아래에 기록된 과거 전체 대화와 동일한 대화 조합은 만들지 않는다:
{json.dumps(used, ensure_ascii=False)}"""
    response = post_json(
        "https://api.openai.com/v1/responses",
        {
            "model": model,
            "store": False,
            "input": [
                {"role": "developer", "content": "교육 내용은 아주 쉽고 정확해야 하며 요청된 JSON 스키마만 출력한다."},
                {"role": "user", "content": prompt},
            ],
            "text": {"format": {"type": "json_schema", "name": "daily_chinese_dialogue", "strict": True, "schema": schema}},
        },
        {"Authorization": f"Bearer {api_key}"},
    )
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return json.loads(content["text"])
    raise SystemExit("OpenAI response did not contain dialogue text")


def short_date(value: date) -> str:
    return f"{value.month}/{value.day}"


def format_message(dialogue: dict, monday: date) -> str:
    sunday = monday + timedelta(days=6)
    parts = [
        "🇨🇳 **오늘의 중국어**",
        "",
        f"**이번 주 회화 ({short_date(monday)}~{short_date(sunday)})**",
        f"**{dialogue['weekly_chinese']}**",
        f"병음: {dialogue['weekly_pinyin']}",
        f"읽기: {dialogue['weekly_korean_pronunciation']}",
        f"뜻: {dialogue['weekly_korean_meaning']}",
        "",
        f"**오늘의 상황: {dialogue['situation']}**",
    ]
    for line in dialogue["lines"]:
        parts.extend([
            "",
            f"👤 {line['speaker']}: **{line['chinese']}**",
            f"병음: {line['pinyin']}",
            f"읽기: {line['korean_pronunciation']}",
            f"뜻: {line['korean_meaning']}",
        ])
    return "\n".join(parts)


def send_discord(webhook_url: str, message: str) -> None:
    parsed = urllib.parse.urlparse(webhook_url)
    if parsed.scheme != "https" or parsed.hostname not in {"discord.com", "discordapp.com"}:
        raise SystemExit("The configured value is not a valid Discord webhook URL")
    post_json(webhook_url, {"content": message}, {"User-Agent": "Chinese-Word-Discord/3.0"})


def main() -> None:
    discord_env = read_env_file(DISCORD_CONFIG)
    openai_env = read_env_file(OPENAI_CONFIG)
    webhook_url = discord_env.get("DISCORD_WEBHOOK_URL", "")
    api_key = openai_env.get("OPENAI_API_KEY", "")
    model = openai_env.get("OPENAI_MODEL", "gpt-5-mini")
    if not webhook_url or not api_key:
        raise SystemExit("DISCORD_WEBHOOK_URL or OPENAI_API_KEY is not set")

    today = datetime.now(TIMEZONE).date()
    date_key = today.isoformat()
    monday = today - timedelta(days=today.weekday())
    monday_key = monday.isoformat()
    history = load_history()
    entries = history.setdefault("dialogues", [])
    existing = next((entry for entry in entries if entry.get("date") == date_key), None)
    if existing and existing.get("sent"):
        return
    if existing:
        send_discord(webhook_url, existing["message"])
        existing["sent"] = True
        save_history(history)
        return

    weekly_conversations = history.setdefault("weekly_conversations", {})
    weekly = weekly_conversations.get(monday_key)
    level, level_text = course_level(today)
    used = [entry.get("signature", "") for entry in entries]
    dialogue = generate_dialogue(api_key, model, weekly, used, level_text)
    signature = " | ".join(line["chinese"] for line in dialogue["lines"])
    if signature in used:
        raise SystemExit("OpenAI generated a duplicate dialogue; nothing was sent")

    weekly_conversations.setdefault(monday_key, {
        "chinese": dialogue["weekly_chinese"],
        "pinyin": dialogue["weekly_pinyin"],
        "korean_pronunciation": dialogue["weekly_korean_pronunciation"],
        "korean_meaning": dialogue["weekly_korean_meaning"],
    })
    message = format_message(dialogue, monday)
    entry = {"date": date_key, "week": monday_key, "level": level, "signature": signature, "message": message, "sent": False}
    entries.append(entry)
    save_history(history)
    send_discord(webhook_url, message)
    entry["sent"] = True
    save_history(history)


if __name__ == "__main__":
    main()
