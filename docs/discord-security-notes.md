# Discord Security Notes

이 프로젝트의 Discord 봇은 아래 3단계로 제한됩니다.

## 1. 설치 제한

- Discord Developer Portal에서 `Public Bot`이 꺼져 있으면, 보통 아무나 자기 서버에 봇을 추가할 수 없습니다.

## 2. 서버 제한

- `.env`의 `CO_AGENT_ALLOWED_GUILD_IDS`는 봇 명령이 실행될 수 있는 Discord 서버 ID 목록입니다.
- 이 목록에 없는 서버에서는 `/bind`, `/send`, `/tail`, `/status`가 모두 거부됩니다.
- 이 값은 "추가 방지"가 아니라 "명령 실행 방지"입니다.

## 3. 사용자 제한

- `.env`의 `CO_AGENT_ALLOWED_USER_IDS`는 봇 명령을 실행할 수 있는 Discord 사용자 ID 목록입니다.
- 허용된 서버 안에서도 이 사용자들만 명령을 실행할 수 있습니다.

## 권장 설정

```env
CO_AGENT_ALLOWED_GUILD_IDS=YOUR_GUILD_ID
CO_AGENT_ALLOWED_USER_IDS=YOUR_USER_ID
CO_AGENT_TEST_GUILD_ID=YOUR_GUILD_ID
```

의미:

- `CO_AGENT_ALLOWED_GUILD_IDS`: 명령 허용 서버
- `CO_AGENT_ALLOWED_USER_IDS`: 명령 허용 사용자
- `CO_AGENT_TEST_GUILD_ID`: 슬래시 명령 빠른 동기화용 개발 설정

## 운영 권장

- `Public Bot`은 끈 상태로 유지
- `CO_AGENT_ALLOWED_GUILD_IDS`에는 본인 서버만 추가
- `CO_AGENT_ALLOWED_USER_IDS`에는 본인 사용자 ID만 추가
- `CO_AGENT_ALLOWED_ROLE_IDS`는 가능하면 사용하지 않거나 최소화
