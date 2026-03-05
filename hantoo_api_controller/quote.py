"""
국내주식 시세(현재가, 호가 등) 조회 API
"""

import logging
from typing import Dict, List, Optional, Union

import pandas as pd

from .api_client import APIResponse, HantooClient
from .config import Config

logger = logging.getLogger(__name__)

ENDPOINT_INQUIRE_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-price"
TR_ID_INQUIRE_PRICE = "FHKST01010100"

ENDPOINT_ASKING_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
TR_ID_ASKING_PRICE = "FHKST01010200"


def get_current_price(
    symbol: str,
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> APIResponse:
    """
    국내주식 종목의 현재가 시세를 조회합니다.
    
    Args:
        symbol: 종목코드 6자리 (예: "005930", "114800")
        config: Config 인스턴스 (미입력 시 환경변수에서 로드)
        client: HantooClient 인스턴스 (미입력 시 config로 생성)
        
    Returns:
        APIResponse. 성공 시 .output 에 시세 정보가 들어 있습니다.
        - stck_prpr: 현재가
        - prdy_vrss: 전일 대비
        - stck_oprc: 시가, stck_hgpr: 고가, stck_lwpr: 저가 등
    """
    cfg = config or Config.load()
    if client is None:
        client = HantooClient(cfg)
    pdno = str(symbol).strip().zfill(6)
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",  # J: 전체(코스피+코스닥)
        "FID_INPUT_ISCD": pdno,
    }
    return client.get(ENDPOINT_INQUIRE_PRICE, TR_ID_INQUIRE_PRICE, params=params)


def current_price_value(
    symbol: str,
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> Optional[int]:
    """
    종목 현재가를 정수(원)로만 반환합니다.
    조회 실패 시 None을 반환합니다.
    """
    resp = get_current_price(symbol, config=config, client=client)
    if not resp.success:
        return None
    out = resp.output
    if not out or not isinstance(out, dict):
        return None
    pr = out.get("stck_prpr")
    if pr is None:
        return None
    try:
        return int(pr)
    except (TypeError, ValueError):
        return None


def get_orderbook(
    symbol: str,
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> APIResponse:
    """
    종목의 매수/매도 호가창(10단계)을 조회합니다.

    Args:
        symbol: 종목코드 6자리

    Returns:
        APIResponse. 성공 시 .output 에 호가 정보 dict.
        - askp1~askp10: 매도호가 (1이 최우선)
        - askp_rsqn1~askp_rsqn10: 매도호가 잔량
        - bidp1~bidp10: 매수호가
        - bidp_rsqn1~bidp_rsqn10: 매수호가 잔량
    """
    cfg = config or Config.load()
    if client is None:
        client = HantooClient(cfg)
    pdno = str(symbol).strip().zfill(6)
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": pdno,
    }
    return client.get(ENDPOINT_ASKING_PRICE, TR_ID_ASKING_PRICE, params=params)


def _get_orderbook_data(resp: APIResponse) -> Optional[dict]:
    """호가 응답에서 output1 dict를 추출합니다."""
    if not resp.success:
        return None
    out = resp.data.get("output1")
    if not out or not isinstance(out, dict):
        return None
    return out


def get_ask_prices(
    symbol: str,
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> List[Dict[str, int]]:
    """
    매도호가 10단계를 [{price, volume}, ...] 형태로 반환합니다.
    가격이 낮은 순(최우선 매도호가부터) 정렬됩니다.
    """
    out = _get_orderbook_data(get_orderbook(symbol, config=config, client=client))
    if out is None:
        return []
    result = []
    for i in range(1, 11):
        price = int(out.get(f"askp{i}", 0))
        volume = int(out.get(f"askp_rsqn{i}", 0))
        if price > 0:
            result.append({"price": price, "volume": volume})
    return result


def get_bid_prices(
    symbol: str,
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> List[Dict[str, int]]:
    """
    매수호가 10단계를 [{price, volume}, ...] 형태로 반환합니다.
    가격이 높은 순(최우선 매수호가부터) 정렬됩니다.
    """
    out = _get_orderbook_data(get_orderbook(symbol, config=config, client=client))
    if out is None:
        return []
    result = []
    for i in range(1, 11):
        price = int(out.get(f"bidp{i}", 0))
        volume = int(out.get(f"bidp_rsqn{i}", 0))
        if price > 0:
            result.append({"price": price, "volume": volume})
    return result


def get_orderbook_df(
    symbol: str,
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> pd.DataFrame:
    """
    호가창을 보기 좋은 DataFrame으로 반환합니다.

    컬럼: 매수잔량 | 가격 | 매도잔량
    매도호가 10단계(위) + 매수호가 10단계(아래) 순서로 정렬됩니다.
    """
    out = _get_orderbook_data(get_orderbook(symbol, config=config, client=client))
    if out is None:
        return pd.DataFrame()

    rows = []
    for i in range(10, 0, -1):
        price = int(out.get(f"askp{i}", 0))
        volume = int(out.get(f"askp_rsqn{i}", 0))
        if price > 0:
            rows.append({"매수잔량": "", "가격": price, "매도잔량": volume})

    for i in range(1, 11):
        price = int(out.get(f"bidp{i}", 0))
        volume = int(out.get(f"bidp_rsqn{i}", 0))
        if price > 0:
            rows.append({"매수잔량": volume, "가격": price, "매도잔량": ""})

    return pd.DataFrame(rows)
