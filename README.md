# Chinese Word Discord

매주 하나의 핵심 중국어 단어·표현을 정하고, 해당 표현을 활용한 초급 일상 문장을 매일 Discord로 보내는 Python 스크립트입니다.

문장은 OpenAI Responses API로 생성합니다. 중국어 원문, 성조가 포함된 병음, 한글식 발음, 자연스러운 한국어 뜻을 함께 제공합니다.

## 동작 방식

- 한 주는 월요일부터 일요일까지입니다.
- 매주 첫 실행에서 핵심 중국어 표현 하나를 선정합니다.
- 그 주에는 같은 핵심 표현을 활용해 매일 서로 다른 문장을 만듭니다.
- 과거에 보낸 중국어 문장과 완전히 동일한 문장은 다시 보내지 않습니다.
- 같은 날짜에 다시 실행해도 이미 전송했다면 건너뜁니다.
- 전송 전에 생성 결과를 기록하므로 Discord 전송이 실패해도 재실행 시 같은 문장을 다시 전송합니다.

## 요구 사항

- Python 3.9 이상
- OpenAI API 키
- Discord 채널 웹훅 URL

외부 Python 패키지는 필요하지 않습니다.

## 설정

예제 설정 파일을 복사합니다.

```bash
cp chinese_word_discord.env.example chinese_word_discord.env
cp chinese_word_discord_openai.env.example chinese_word_discord_openai.env
cp chinese_word_discord_history.json.example chinese_word_discord_history.json
```

`chinese_word_discord.env`에 Discord 웹훅 URL을 입력합니다.

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

`chinese_word_discord_openai.env`에 OpenAI API 키와 모델을 입력합니다.

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5-mini
```

실제 키가 들어 있는 설정 파일은 `.gitignore`에 포함되어 Git에 커밋되지 않습니다. 문장 중복 방지를 위한 `chinese_word_discord_history.json`에는 비밀값이 없으며, GitHub Actions 실행 간 기록을 이어가기 위해 저장소에 커밋됩니다.

## 실행

```bash
python3 chinese_word_discord.py
```

성공하면 별도 출력 없이 종료합니다. 생성된 문장과 주간 주제는 `chinese_word_discord_history.json`에 저장됩니다.

## GitHub Actions 자동 실행

저장소의 `Settings` → `Secrets and variables` → `Actions`에 다음 Repository Secret 두 개를 등록합니다.

- `OPENAI_API_KEY`
- `DISCORD_WEBHOOK_URL`

포함된 워크플로는 매일 오후 9시 58분(한국 시간)에 실행됩니다. 실행 후 갱신된 `chinese_word_discord_history.json`을 저장소에 자동 커밋해, 다음 실행에서도 과거 문장의 중복을 검사할 수 있게 합니다.

GitHub Actions의 예약 워크플로는 서버 상황에 따라 정각보다 조금 늦게 시작될 수 있습니다. `Actions` 탭의 `Send daily Chinese sentence`에서 `Run workflow`를 눌러 수동으로 시험할 수도 있습니다.

## 로컬 자동 실행 예시

한국 시간 기준 매일 오후 9시 58분에 실행하는 cron 예시입니다. `/absolute/path`는 실제 프로젝트 경로로 바꾸세요.

```cron
58 21 * * * cd /absolute/path/chinese-word-discord && /usr/bin/python3 chinese_word_discord.py
```

컴퓨터가 꺼져 있거나 잠자기 상태이면 로컬 예약 실행이 동작하지 않을 수 있습니다. 항상 실행하려면 서버나 GitHub Actions 같은 별도 실행 환경을 사용할 수 있습니다. 이 경우 비밀값은 저장소 파일이 아니라 해당 서비스의 Secrets 기능에 등록하세요.

## 보안

- OpenAI API 키와 Discord 웹훅 URL을 코드나 커밋에 넣지 마세요.
- 비밀값이 노출되었다면 즉시 해당 키 또는 웹훅을 폐기하고 새로 발급하세요.
- 공개 저장소에 올리기 전 `git status`와 커밋 내용을 확인하세요.
