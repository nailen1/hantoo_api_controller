"""
국내주식 시세(현재가 등) 조회 API
"""

import logging
from typing import Optional, Union

from .api_client import APIResponse, HantooClient
from .config import Config

logger = logging.getLogger(__name__)

ENDPOINT_INQUIRE_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-price"
TR_ID_INQUIRE_PRICE = "FHKST01010100"


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
