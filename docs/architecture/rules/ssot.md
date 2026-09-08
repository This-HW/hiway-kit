# SSOT (Single Source of Truth) 원칙

> 이 문서는 코드베이스에서 단일 진실 공급원 원칙을 적용하는 방법을 설명합니다.

---

## 1. 핵심 원칙

```
ALWAYS define error types, API endpoints, and env vars in exactly one file.
NEVER copy values — always reference via import.
ALWAYS structure code so one change propagates everywhere.
```

**왜 SSOT가 중요한가?**

같은 값이 여러 곳에 흩어져 있으면:

- 하나를 바꿀 때 나머지를 빠뜨려서 버그 발생
- 어떤 값이 "진짜"인지 알 수 없어 혼란
- 버그가 여러 곳에 동시에 나타나 디버깅 어려움

---

## 2. SSOT 위반 vs 적용 예시

### Before (위반) — API 도메인이 여러 모듈에 분산

```
user 모듈:  https://api.example.com/v1/users 로 직접 요청
order 모듈: https://api.example.com/v1/orders 로 직접 요청
auth 모듈:  https://api.example.com/v1/auth/login 으로 직접 요청
```

**문제:** API 도메인이 변경되면 관련 모듈을 모두 수정해야 함. 하나라도 빠뜨리면 버그.

---

### After (적용) — 단일 설정 참조

```
config 모듈 (단일 소스):
  API_BASE_URL = 환경변수 또는 기본값
  API_URL      = API_BASE_URL + API_VERSION

user/order/auth 모듈:
  config에서 API_URL을 참조(언어별 관례대로 import/include/require)해
  `${API_URL}/users` 같은 형태로만 사용 — 도메인 문자열을 직접 쓰지 않는다
```

**효과:** API_BASE_URL 한 곳만 바꾸면 전체에 적용.

---

## 3. 에러 로깅 아키텍처

에러 처리는 SSOT 원칙이 가장 자주 위반되는 영역입니다. 중앙 핸들러 하나를 통해 모든 에러를 처리합니다.

```
에러 발생 위치 (서비스, 컨트롤러, 미들웨어 등)
          │
          ▼
  errors 모듈 — 언어/프레임워크 관례대로 파일을 나눈다 (예시일 뿐, 강제하지 않는다):
  · 에러 타입/코드 정의
  · 에러 메시지 상수
  · 중앙 핸들러 (정규화 + 알림)
  · 구조화된 로거
          │
          ▼
    중앙 에러 핸들러
    ├── 에러 정규화 (알 수 없는 예외 → 공통 에러 타입)
    ├── 심각도에 따른 알림 (critical → 온콜 채널)
    └── 구조화된 로그 기록
```

---

## 4. 에러 로그 필드 정의

| 필드        | 타입   | 필수 여부 | 설명                                 | 예시                           |
| ----------- | ------ | --------- | ------------------------------------ | ------------------------------ |
| `code`      | string | 필수      | 에러 식별 코드                       | `AUTH_001`, `PAYMENT_003`      |
| `message`   | string | 필수      | 사람이 읽을 수 있는 설명             | `"인증 토큰이 만료되었습니다"` |
| `timestamp` | string | 필수      | ISO 8601 형식                        | `"2024-01-15T09:23:11.000Z"`   |
| `severity`  | enum   | 필수      | `debug\|info\|warn\|error\|critical` | `"error"`                      |
| `userId`    | string | 선택      | 관련 사용자 ID                       | `"user_abc123"`                |
| `requestId` | string | 선택      | 요청 추적 ID                         | `"req_xyz789"`                 |
| `stack`     | string | 선택      | 스택 트레이스 (개발환경)             | `"Error: ...\n  at ..."`       |
| `cause`     | Error  | 선택      | 원인 에러 체인                       | 원본 에러 객체                 |

---

## 5. 에러 코드 네이밍 규칙

```
에러 타입 정의 (한 곳):
  AUTH_001  = 인증 실패
  AUTH_002  = 토큰 만료
  AUTH_003  = 권한 없음
  PAYMENT_001 = 결제 실패
  PAYMENT_002 = 잔액 부족
  DB_001    = DB 연결 실패
  (도메인_번호 형식 — 언어의 enum/상수 맵/딕셔너리 등 관례로 표현)

메시지 정의 (별도의 한 곳, 코드와 1:1 매핑):
  AUTH_001  → "인증에 실패했습니다"
  AUTH_002  → "인증 토큰이 만료되었습니다"
  ...
```

---

## 6. 실전 예시: DB SSH Tunnel (SSOT 위반 → 적용)

### 위반 케이스 — 터널 연결 명령이 여러 스크립트에 중복

```bash
# scripts/migrate.sh
ssh -L 5432:db.internal:5432 bastion.example.com -N &
psql postgresql://localhost:5432/mydb -f migrations/

# scripts/backup.sh
ssh -L 5432:db.internal:5432 bastion.example.com -N &  # 복붙!
pg_dump postgresql://localhost:5432/mydb > backup.sql

# scripts/seed.sh
ssh -L 5432:db.internal:5432 bastion.example.com -N &  # 또 복붙!
psql postgresql://localhost:5432/mydb -f seed.sql
```

**문제:** bastion 주소나 포트가 바뀌면 3개 파일 모두 수정해야 함.

---

### 적용 케이스 — 단일 터널 스크립트 참조

```bash
# scripts/db-tunnel.sh (단일 소스)
#!/bin/bash
DB_HOST="${DB_HOST:-db.internal}"
DB_PORT="${DB_PORT:-5432}"
BASTION="${BASTION_HOST:-bastion.example.com}"
LOCAL_PORT="${LOCAL_PORT:-5432}"

case "$1" in
  start) ssh -L "${LOCAL_PORT}:${DB_HOST}:${DB_PORT}" "${BASTION}" -N & ;;
  stop)  pkill -f "ssh -L ${LOCAL_PORT}" ;;
esac

# scripts/migrate.sh
source scripts/db-tunnel.sh start
psql postgresql://localhost:5432/mydb -f migrations/
source scripts/db-tunnel.sh stop

# scripts/backup.sh
source scripts/db-tunnel.sh start  # 항상 같은 출처
pg_dump postgresql://localhost:5432/mydb > backup.sql
source scripts/db-tunnel.sh stop
```

**효과:** bastion 변경 시 `db-tunnel.sh` 하나만 수정.

---

## 7. SSOT 체크리스트

코드를 작성하거나 리뷰할 때 아래 질문을 합니다.

| 질문                                           | SSOT 위반 신호                      | 해결 방법            |
| ---------------------------------------------- | ----------------------------------- | -------------------- |
| 이 값이 다른 곳에 이미 정의되어 있는가?        | 같은 문자열/숫자가 여러 파일에 존재 | import로 참조        |
| 이 하드코딩된 값이 나중에 바뀔 수 있는가?      | 매직 넘버/매직 문자열 사용          | 명명된 상수로 추출   |
| 이 에러가 중앙 핸들러를 통하는가?              | catch 블록에 `console.log`만 있음   | 중앙 핸들러로 라우팅 |
| 이 값을 바꾸려면 몇 개 파일을 수정해야 하는가? | 10개 이상 파일 수정 필요            | SSOT 구조 설계 필요  |
| 같은 버그가 여러 곳에서 동시에 나타났는가?     | 동일한 패턴의 버그가 반복           | 중복 코드 단일화     |
