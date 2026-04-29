---
icon: lucide/shield
---

# Security Notes

이 프로젝트는 Discord와 Telegram 양쪽 모두에서 사용자/채팅 단위로 명령 실행을 제한합니다.

## Discord

### 1. 설치 제한

- Discord Developer Portal에서 `Public Bot`이 꺼져 있으면, 보통 아무나 자기 서버에 봇을 추가할 수 없습니다.

### 2. 서버 제한

- `.env`의 `TETHERLY_ALLOWED_GUILD_IDS`는 봇 명령이 실행될 수 있는 Discord 서버 ID 목록입니다.
- 이 목록에 없는 서버에서는 `/bind`, `/send`, `/tail`, `/status`가 모두 거부됩니다.
- 이 값은 "추가 방지"가 아니라 "명령 실행 방지"입니다.

### 3. 사용자 제한

- `.env`의 `TETHERLY_ALLOWED_USER_IDS`는 봇 명령을 실행할 수 있는 Discord 사용자 ID 목록입니다.
- 허용된 서버 안에서도 이 사용자들만 명령을 실행할 수 있습니다.

### 권장 설정

```env
TETHERLY_ALLOWED_GUILD_IDS=YOUR_GUILD_ID
TETHERLY_ALLOWED_USER_IDS=YOUR_USER_ID
TETHERLY_TEST_GUILD_ID=YOUR_GUILD_ID
```

의미:

- `TETHERLY_ALLOWED_GUILD_IDS`: 명령 허용 서버
- `TETHERLY_ALLOWED_USER_IDS`: 명령 허용 사용자
- `TETHERLY_TEST_GUILD_ID`: 슬래시 명령 빠른 동기화용 개발 설정

### 운영 권장

- `Public Bot`은 끈 상태로 유지
- `TETHERLY_ALLOWED_GUILD_IDS`에는 본인 서버만 추가
- `TETHERLY_ALLOWED_USER_IDS`에는 본인 사용자 ID만 추가
- `TETHERLY_ALLOWED_ROLE_IDS`는 가능하면 사용하지 않거나 최소화

## Telegram

### 1. 토큰

- `TELEGRAM_BOT_TOKEN`은 봇 인증의 전부입니다. 노출되면 누구나 봇으로 메시지를 보낼 수 있고, 우리 봇이 받는 업데이트도 빼앗아갈 수 있습니다 (텔레그램은 한 토큰당 한 클라이언트만 polling 가능).
- 유출 시 [@BotFather](https://t.me/BotFather)에서 `/revoke` → 새 토큰 발급 → `tetherly config edit`로 갱신 후 봇 재시작.

### 2. 사용자 제한

- `.env`의 `TETHERLY_TELEGRAM_ALLOWED_USER_IDS`는 봇 명령을 실행할 수 있는 Telegram 사용자 ID 목록입니다.
- **목록이 비어 있으면 아무도 명령을 실행할 수 없습니다** (디스코드와 동일한 fail-closed 동작).
- 이 allowlist에 없는 사용자가 `/bind` 등을 보내면 봇은 "You are not allowed to use this command." 로 응답하고 동작하지 않습니다.

### 3. 채팅 제한 (선택)

- `.env`의 `TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS`는 명령이 실행될 수 있는 chat ID 목록입니다 (개인 chat은 본인 user ID, 그룹은 음수 ID).
- 비어 있으면 user allowlist만으로 제한합니다. 보통 개인용 봇이라면 user allowlist만으로 충분합니다.

### 4. Privacy mode

- BotFather의 봇 privacy mode가 켜져 있으면 그룹에서 슬래시 명령어 외 일반 메시지가 봇에 전달되지 않습니다.
- `/config on` (auto-send) 기능을 그룹에서 쓰려면 privacy mode를 꺼야 하지만, **꺼진 봇은 그룹의 모든 메시지를 받게 되므로** 가능하면 개인 chat에서만 쓰는 것을 권장합니다. 자세한 절차는 [Telegram setup](telegram-setup.md#3-group-chat-only-disable-privacy-mode) 참고.

### 권장 설정

```env
TELEGRAM_BOT_TOKEN=...                  # @BotFather에서 발급
TETHERLY_TELEGRAM_ALLOWED_USER_IDS=YOUR_USER_ID
# TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS=YOUR_CHAT_ID   # 필요할 때만
```

### 운영 권장

- 봇은 가급적 개인 chat (DM)에서만 사용 — privacy mode를 끌 필요가 없음
- 그룹에서 써야 한다면 `TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS`도 같이 설정
- 토큰은 절대 git에 커밋하지 말 것 (`~/.tetherly/.env`는 `chmod 600`으로 자동 설정됨)
