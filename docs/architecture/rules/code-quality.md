# 코드 품질 규칙

> 이 문서는 claude-code-kit에서 적용하는 코드 품질 기준과 그 이유를 설명합니다.

---

## 1. 함수 크기 제한

| 기준        | 허용    | 금지   | 이유                                   |
| ----------- | ------- | ------ | -------------------------------------- |
| 줄 수       | ≤ 20줄  | 50줄+  | 20줄 초과 시 단일 책임 원칙 위반 신호  |
| 파라미터 수 | ≤ 3개   | 5개+   | 파라미터 4개 이상이면 객체로 묶어야 함 |
| 중첩 깊이   | ≤ 2단계 | 4단계+ | 깊은 중첩은 Early Return으로 대체 가능 |

### 파라미터 줄이기 — 객체 패턴

```typescript
// ❌ 파라미터 5개 — 호출 시 순서 헷갈림, 가독성 저하
function createUser(name: string, email: string, age: number, role: string, isActive: boolean) { ... }

// ✅ 객체로 묶기 — 이름이 있어서 순서 무관, 선택적 필드 명확
interface CreateUserOptions {
  name: string;
  email: string;
  age: number;
  role: string;
  isActive?: boolean; // 선택적 필드
}

function createUser(options: CreateUserOptions) { ... }
```

---

## 2. 네이밍 가이드

함수명과 변수명은 코드의 의도를 표현합니다. 주석 없이도 이해되어야 합니다.

### 함수명

| 좋은 예               | 나쁜 예    | 이유                     |
| --------------------- | ---------- | ------------------------ |
| `calculateTotalPrice` | `calc`     | 무엇을 계산하는지 불명확 |
| `validateUserInput`   | `validate` | 무엇을 검증하는지 불명확 |
| `sendWelcomeEmail`    | `send`     | 무엇을 보내는지 불명확   |
| `getUserById`         | `getUser`  | 어떻게 가져오는지 불명확 |
| `isEmailVerified`     | `check`    | boolean 반환 여부 불명확 |
| `handlePaymentError`  | `doStuff`  | 아무 의미 없음           |

### 변수명

```typescript
// ❌ 나쁜 예 — 맥락 없이는 의미 파악 불가
const d = new Date();
const u = await getUser(id);
const arr = items.filter((i) => i.active);
const val = price * 0.1;

// ✅ 좋은 예 — 이름만으로 역할 파악 가능
const createdAt = new Date();
const currentUser = await getUser(id);
const activeItems = items.filter((item) => item.isActive);
const taxAmount = price * TAX_RATE;
```

---

## 3. 단일 책임 원칙 (SRP)

한 함수는 한 가지 일만 합니다. 함수가 여러 일을 하면 테스트가 어렵고, 변경 시 영향 범위가 커집니다.

```typescript
// ❌ 잘못된 예 — 한 함수가 저장 + 이메일 전송 + 로깅
async function registerUser(userData: UserData) {
  const user = await db.users.create(userData);
  await emailService.sendWelcomeEmail(user.email); // 저장과 무관한 작업
  logger.info(`User created: ${user.id}`); // 또 다른 책임
  return user;
}

// ✅ 올바른 예 — 각 함수는 하나의 책임
async function saveUser(userData: UserData): Promise<User> {
  return db.users.create(userData);
}

async function sendWelcomeEmail(email: string): Promise<void> {
  await emailService.send({ to: email, template: "welcome" });
}

function logUserCreation(userId: string): void {
  logger.info(`User created: ${userId}`);
}

// 조율은 상위 함수에서
async function registerUser(userData: UserData): Promise<User> {
  const user = await saveUser(userData);
  await sendWelcomeEmail(user.email);
  logUserCreation(user.id);
  return user;
}
```

---

## 4. 에러 처리 패턴

에러를 무시하거나 `console.log`만 하면 운영 환경에서 원인 파악이 불가능합니다.

```typescript
// ❌ 잘못된 예 — 에러 무시
try {
  await processPayment(order);
} catch (error) {
  console.log(error); // 운영에서 이 로그는 사라짐
}

// ❌ 잘못된 예 — 에러 타입 무시
try {
  await processPayment(order);
} catch (error) {
  throw new Error("결제 실패"); // 원본 에러 정보 소실
}

// ✅ 올바른 예 — 타입별 처리 + 컨텍스트 보존
try {
  await processPayment(order);
} catch (error) {
  if (error instanceof NetworkError) {
    return handleNetworkError(error); // 재시도 로직
  }
  if (error instanceof ValidationError) {
    return handleValidationError(error); // 사용자 피드백
  }
  if (error instanceof PaymentGatewayError) {
    logger.error("결제 게이트웨이 오류", { orderId: order.id, error });
    throw new AppError({
      code: "PAYMENT_GATEWAY_ERROR",
      message: `주문 ${order.id} 결제 처리 실패`,
      cause: error, // 원본 에러 체인 유지
    });
  }
  throw error; // 알 수 없는 에러는 상위로 전파
}
```

---

## 5. Early Return 패턴

중첩 조건문은 Early Return으로 대체해 읽기 쉽게 만듭니다.

```typescript
// ❌ 깊은 중첩 — 화살표 안티패턴
function processOrder(user: User | null, order: Order | null) {
  if (user) {
    if (user.isActive) {
      if (order) {
        if (order.status === "pending") {
          // 실제 로직이 여기 있음 — 4단계 중첩
          return fulfillOrder(user, order);
        }
      }
    }
  }
  return null;
}

// ✅ Early Return — 실패 조건 먼저 처리
function processOrder(user: User | null, order: Order | null) {
  if (!user) return null;
  if (!user.isActive) return null;
  if (!order) return null;
  if (order.status !== "pending") return null;

  // 모든 조건이 충족된 경우만 여기 도달
  return fulfillOrder(user, order);
}
```

---

## 6. 타입 안전성 규칙

```typescript
// ❌ any 사용 — 타입 시스템 무력화
function processData(data: any) {
  return data.userId; // 런타임 오류 위험
}

// ✅ 명시적 타입
function processData(data: UserPayload): string {
  return data.userId;
}

// ❌ 과도한 타입 단언
const user = response.data as User; // 타입 검증 없이 강제 캐스팅

// ✅ 타입 가드
function isUser(data: unknown): data is User {
  return (
    typeof data === "object" && data !== null && "id" in data && "email" in data
  );
}

const rawData = response.data;
if (isUser(rawData)) {
  // 여기서부터 User 타입 보장
  console.log(rawData.email);
}

// ❌ null 체크 생략
const name = user.profile.name; // user나 profile이 null이면 런타임 오류

// ✅ 옵셔널 체이닝 + null 병합
const name = user?.profile?.name ?? "Unknown";
```

---

## 7. 테스트 가능성 — 의존성 주입

테스트하기 어려운 코드는 대부분 의존성이 하드코딩되어 있습니다.

```typescript
// ❌ 테스트 불가 — Database가 하드코딩됨
class UserService {
  async getUser(id: string): Promise<User> {
    const db = new Database(); // 테스트 시 실제 DB 연결 시도
    return db.users.findById(id);
  }
}

// ✅ 테스트 가능 — 인터페이스 기반 의존성 주입
interface IDatabase {
  users: {
    findById(id: string): Promise<User>;
  };
}

class UserService {
  constructor(private db: IDatabase) {} // 외부에서 주입

  async getUser(id: string): Promise<User> {
    return this.db.users.findById(id);
  }
}

// 프로덕션: 실제 DB 주입
const service = new UserService(new PostgresDatabase());

// 테스트: Mock DB 주입
const mockDb: IDatabase = {
  users: { findById: jest.fn().mockResolvedValue(testUser) },
};
const testService = new UserService(mockDb);
```

---

## 8. 코드 품질 체크리스트

구현 완료 전 아래 항목을 확인합니다.

### 함수/구조

- [ ] 함수가 20줄 이하인가?
- [ ] 파라미터가 3개 이하인가? (초과 시 객체로 묶기)
- [ ] 중첩 깊이가 2단계 이하인가?
- [ ] 각 함수가 단일 책임을 가지는가?

### 네이밍

- [ ] 함수명이 동사+명사로 구체적인가? (`calc` → `calculateTotalPrice`)
- [ ] 변수명에 의미가 담겨있는가? (`d` → `createdAt`)
- [ ] boolean 변수명이 `is/has/can`으로 시작하는가?

### 타입 안전성

- [ ] `any`를 사용하지 않았는가?
- [ ] null/undefined 체크가 되어 있는가?
- [ ] 타입 단언(`as`) 대신 타입 가드를 사용했는가?

### 에러 처리

- [ ] 에러를 무시하거나 `console.log`만 하지 않았는가?
- [ ] 에러 타입별로 다르게 처리하는가?
- [ ] 에러 컨텍스트(ID, 상태 등)가 포함되어 있는가?

### 테스트 가능성

- [ ] 의존성이 생성자 주입으로 되어 있는가?
- [ ] 순수 함수 (같은 입력 → 같은 출력)인가?
- [ ] 전역 상태를 직접 수정하지 않는가?
