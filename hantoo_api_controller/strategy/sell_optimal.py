"""
최적 매도호가 전략

호가창에서 매도 매물대가 두꺼운 가격을 파악하여 해당 가격에 매도 주문을 넣고,
일정 시간 내 미체결 시 취소 후 재시도합니다.
"""

import logging
import time
from typing import Optional

from ..session import HantooSession

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 300
DEFAULT_POLL_INTERVAL_SEC = 10


def _find_optimal_ask_price(session: HantooSession, symbol: str) -> Optional[int]:
    """
    호가창에서 매도 매물대가 가장 두꺼운(잔량이 가장 많은) 가격을 찾습니다.
    현재가 이상의 매도호가 중 최대 잔량 호가를 반환합니다.
    """
    asks = session.get_ask_prices(symbol)
    if not asks:
        return None

    best = max(asks, key=lambda x: x["volume"])
    return best["price"]


def _check_order_filled(
    session: HantooSession,
    odno: str,
) -> bool:
    """주문번호로 체결 여부를 확인합니다."""
    orders, _ = session.get_order_history(ccld_dvsn="00", odno=odno)
    if orders.empty:
        return False

    col_remaining = "잔여수량" if "잔여수량" in orders.columns else "rmn_qty"
    if col_remaining not in orders.columns:
        return False

    row = orders.iloc[0]
    return int(row[col_remaining]) == 0


def sell_at_optimal_ask(
    session: HantooSession,
    symbol: str,
    quantity: int,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    poll_interval_sec: int = DEFAULT_POLL_INTERVAL_SEC,
    max_retries: int = 10,
) -> dict:
    """
    호가창 매도 매물대 분석 후 최적 가격에 매도 주문을 넣습니다.
    timeout_sec 이내 미체결 시 취소 후 재시도합니다.

    Args:
        session: HantooSession 인스턴스
        symbol: 종목코드 6자리
        quantity: 매도 수량
        timeout_sec: 체결 대기 시간 (초, 기본 300초=5분)
        poll_interval_sec: 체결 확인 간격 (초, 기본 10초)
        max_retries: 최대 재시도 횟수 (기본 10)

    Returns:
        dict: {
            "success": bool,
            "filled_price": int or None,
            "attempts": int,
            "message": str,
        }
    """
    symbol = str(symbol).strip().zfill(6)

    for attempt in range(1, max_retries + 1):
        # 1) 호가창에서 최적 매도 가격 탐색
        ask_price = _find_optimal_ask_price(session, symbol)
        if ask_price is None:
            logger.warning("[시도 %d] 호가 조회 실패, 재시도", attempt)
            time.sleep(poll_interval_sec)
            continue

        logger.info(
            "[시도 %d] %s 최적 매도호가: %s원 × %d주",
            attempt, symbol, f"{ask_price:,}", quantity,
        )

        # 2) 지정가 매도 주문
        body = session.build_sell_order_body(
            symbol, quantity, order_type="limit", price=ask_price
        )
        resp = session.sell(body)

        if not resp.success:
            logger.warning("[시도 %d] 매도 주문 실패: %s", attempt, resp.message)
            return {
                "success": False,
                "filled_price": None,
                "attempts": attempt,
                "message": f"주문 실패: {resp.message}",
            }

        odno = resp.data.get("output", {}).get("ODNO", "")
        krx_orgno = resp.data.get("output", {}).get("KRX_FWDG_ORD_ORGNO", "")
        logger.info("[시도 %d] 주문 접수 (주문번호: %s)", attempt, odno)

        # 3) 체결 대기
        elapsed = 0
        filled = False
        while elapsed < timeout_sec:
            time.sleep(poll_interval_sec)
            elapsed += poll_interval_sec

            if _check_order_filled(session, odno):
                filled = True
                break

            logger.debug(
                "[시도 %d] 미체결 대기 중... %d/%d초", attempt, elapsed, timeout_sec
            )

        if filled:
            logger.info(
                "[시도 %d] 체결 완료: %s %s원 × %d주",
                attempt, symbol, f"{ask_price:,}", quantity,
            )
            return {
                "success": True,
                "filled_price": ask_price,
                "attempts": attempt,
                "message": "체결 완료",
            }

        # 4) 미체결 → 주문 취소
        logger.info("[시도 %d] %d초 경과 미체결, 주문 취소", attempt, timeout_sec)
        cancel_resp = session.cancel_order(odno, krx_orgno)
        if not cancel_resp.success:
            logger.warning("[시도 %d] 주문 취소 실패: %s", attempt, cancel_resp.message)

        time.sleep(1)

    return {
        "success": False,
        "filled_price": None,
        "attempts": max_retries,
        "message": f"{max_retries}회 시도 후 미체결",
    }
