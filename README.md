# hantoo_api_controller

한국투자증권 Open API를 Python으로 간편하게 사용하기 위한 컨트롤러 패키지입니다.

## 주요 기능

- **세션 기반 토큰 관리** — 토큰을 1회 발급하고 재사용하며, 파일 캐시로 커널 재시작 시에도 유지
- **계좌 잔고 조회** — 보유종목, 평가손익, 예수금 등 계좌 전체 현황
- **현재가 조회** — 종목코드로 실시간 현재가 조회
- **매수/매도 주문** — 지정가·시장가 주문 바디 생성 및 전송
- **금액 기준 매수/매도** — 총 투자금액을 입력하면 매수·매도 가능 수량을 자동 환산
- **주문 체결 내역 조회** — 일별 주문·체결 내역 조회
- **한국어 컬럼 변환** — API 응답의 영문 컬럼명을 한국어 전문 용어로 변환

## 설치

```bash
git clone https://github.com/nailen1/hantoo_api_controller.git
cd hantoo_api_controller
python -m venv env-hantoo
source env-hantoo/bin/activate
pip install -r requirements.txt
```

## 환경 설정

`.env.example`을 복사하여 `.env` 파일을 만들고 실제 값을 입력합니다.

```bash
cp .env.example .env
```

```
HANTOO_APP_KEY=your_app_key_here
HANTOO_APP_SECRET=your_app_secret_here
HANTOO_ACCOUNT_NO=12345678
HANTOO_ACCOUNT_PRODUCT_CODE=01
HANTOO_ENV=demo
```

API 키는 [한국투자증권 개발자센터](https://apiportal.koreainvestment.com/)에서 발급받을 수 있습니다.

## 사용법

```python
from hantoo_api_controller import HantooSession

session = HantooSession()
```

### 계좌 잔고 조회

```python
holdings, summary = session.get_info_account(option_kor_cols=True)
```

### 현재가 조회

```python
price = session.current_price_value("005930")
```

### 매수 주문

```python
# 수량 지정
body = session.build_buy_order_body("005930", quantity=10, order_type="limit", price=70000)

# 금액 기준 (현재가 자동 조회)
body = session.build_buy_order_body_by_amount("005930", amount=1_000_000)

# 주문 전송
resp = session.buy(body)
```

### 매도 주문

```python
# 수량 지정
body = session.build_sell_order_body("005930", quantity=10, order_type="limit", price=70000)

# 금액 기준 (현재가 자동 조회)
body = session.build_sell_order_body_by_amount("005930", amount=1_000_000)

# 주문 전송
resp = session.sell(body)
```

### 주문 체결 내역 조회

```python
orders, order_summary = session.get_order_history(option_kor_cols=True)
```

## 프로젝트 구조

```
hantoo_api_controller/
├── __init__.py       # 패키지 진입점
├── config.py         # 환경변수 로드 및 설정 관리
├── consts.py         # 컬럼명 한국어 매핑 상수
├── auth.py           # OAuth 토큰 발급 및 파일 캐시
├── api_client.py     # HTTP 요청 클라이언트
├── session.py        # 세션 클래스 (주요 인터페이스)
├── account.py        # 계좌 잔고 조회
├── quote.py          # 현재가 시세 조회
└── order.py          # 매수/매도 주문, 체결 내역 조회
```

## 토큰 캐시

토큰은 `.cache/token_cache.json`에 자동 저장되며, 만료 30분 전에 자동 갱신됩니다. 커널을 재시작하거나 새 세션을 생성해도 유효한 토큰을 재사용합니다.

## 라이선스

MIT
