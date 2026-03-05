"""
주문 관련 API 함수 모듈 (매수/매도/체결조회)
"""

import json
import logging
from datetime import datetime
from typing import Literal, Optional, Tuple, Union

import pandas as pd

from .api_client import APIResponse, HantooClient
from .config import Config
from .consts import MAPPING_KOR_COLUMNS

logger = logging.getLogger(__name__)

ORD_DVSN_LIMIT = "00"
ORD_DVSN_MARKET = "01"

TR_ID_SELL_REAL = "TTTC0011U"
TR_ID_SELL_DEMO = "VTTC0011U"

TR_ID_BUY_REAL = "TTTC0012U"
TR_ID_BUY_DEMO = "VTTC0012U"

TR_ID_CCLD_REAL = "TTTC0081R"
TR_ID_CCLD_DEMO = "VTTC0081R"

TR_ID_CANCEL_REAL = "TTTC0013U"
TR_ID_CANCEL_DEMO = "VTTC0013U"

ENDPOINT_ORDER_CASH = "/uapi/domestic-stock/v1/trading/order-cash"
ENDPOINT_ORDER_RVSECNCL = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
ENDPOINT_INQUIRE_DAILY_CCLD = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"


def build_sell_order_body(
    symbol: str,
    quantity: int,
    order_type: Literal["limit", "market"] = "limit",
    price: Optional[Union[int, float]] = None,
    *,
    config: Optional[Config] = None,
) -> dict:
    """
    매도 주문용 API 요청 body(dict)를 생성합니다.
    POST 호출은 하지 않습니다.
    
    Args:
        symbol: 종목코드 (6자리, 예: "005930")
        quantity: 매도 수량
        order_type: "limit" 지정가 / "market" 시장가
        price: 지정가 주문일 때 호가(단가). 시장가면 무시됨.
        config: Config 인스턴스 (미입력 시 환경변수에서 로드, CANO/ACNT_PRDT_CD용)
        
    Returns:
        API order-cash 요청 body (dict). CANO, ACNT_PRDT_CD, PDNO, ORD_DVSN, ORD_QTY, ORD_UNPR 포함.
        
    Example:
        >>> body = build_sell_order_body("005930", 10, "limit", price=70000)
        >>> resp = sell(body)
    """
    cfg = config or Config.load()
    if order_type == "market":
        ord_dvsn = ORD_DVSN_MARKET
        ord_unpr = "0"
    else:
        ord_dvsn = ORD_DVSN_LIMIT
        if price is None:
            raise ValueError("지정가 주문 시 price(호가)를 입력해야 합니다.")
        ord_unpr = str(int(price))
    pdno = str(symbol).strip().zfill(6)
    return {
        "CANO": cfg.account_no,
        "ACNT_PRDT_CD": cfg.account_product_code,
        "PDNO": pdno,
        "ORD_DVSN": ord_dvsn,
        "ORD_QTY": str(quantity),
        "ORD_UNPR": ord_unpr,
        "EXCG_ID_DVSN_CD": "KRX",
        "SLL_TYPE": "01",
        "CNDT_PRIC": "",
    }


def sell(
    body: dict,
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> APIResponse:
    """
    매도 주문 body를 받아 order-cash API로 POST 요청을 보냅니다.
    주문 내용은 build_sell_order_body()로 생성한 dict를 넘깁니다.
    
    Args:
        body: 주문 body (build_sell_order_body() 반환값 또는 동일 형식의 dict)
        config: Config 인스턴스 (미입력 시 환경변수에서 로드, tr_id/실전·모의 구분용)
        client: HantooClient 인스턴스 (미입력 시 config로 생성)
        
    Returns:
        APIResponse (.success, .message, .data 등)
        
    Example:
        >>> body = build_sell_order_body("005930", 10, "limit", price=70000)
        >>> resp = sell(body)
    """
    cfg = config or Config.load()
    if client is None:
        client = HantooClient(cfg)
    tr_id = TR_ID_SELL_REAL if cfg.is_real else TR_ID_SELL_DEMO
    extra_headers = {"custtype": "P"}
    body_str = json.dumps(body, ensure_ascii=False)
    response = client.post(
        ENDPOINT_ORDER_CASH, tr_id, extra_headers=extra_headers, body_json_str=body_str
    )
    pdno = body.get("PDNO", "")
    quantity = body.get("ORD_QTY", "")
    if response.success:
        logger.info("매도 주문 성공: %s %s주 %s", pdno, quantity, response.message)
    else:
        logger.warning("매도 주문 실패: %s", response.message)
    return response


def build_buy_order_body(
    symbol: str,
    quantity: int,
    order_type: Literal["limit", "market"] = "limit",
    price: Optional[Union[int, float]] = None,
    *,
    config: Optional[Config] = None,
) -> dict:
    """
    매수 주문용 API 요청 body(dict)를 생성합니다.
    POST 호출은 하지 않습니다.
    
    Args:
        symbol: 종목코드 (6자리, 예: "005930")
        quantity: 매수 수량
        order_type: "limit" 지정가 / "market" 시장가
        price: 지정가 주문일 때 호가(단가). 시장가면 무시됨.
        config: Config 인스턴스 (미입력 시 환경변수에서 로드, CANO/ACNT_PRDT_CD용)
        
    Returns:
        API order-cash 요청 body (dict). CANO, ACNT_PRDT_CD, PDNO, ORD_DVSN, ORD_QTY, ORD_UNPR 포함.
        
    Example:
        >>> body = build_buy_order_body("005930", 10, "limit", price=70000)
        >>> resp = buy(body)
    """
    cfg = config or Config.load()
    if order_type == "market":
        ord_dvsn = ORD_DVSN_MARKET
        ord_unpr = "0"
    else:
        ord_dvsn = ORD_DVSN_LIMIT
        if price is None:
            raise ValueError("지정가 주문 시 price(호가)를 입력해야 합니다.")
        ord_unpr = str(int(price))
    pdno = str(symbol).strip().zfill(6)
    return {
        "CANO": cfg.account_no,
        "ACNT_PRDT_CD": cfg.account_product_code,
        "PDNO": pdno,
        "ORD_DVSN": ord_dvsn,
        "ORD_QTY": str(quantity),
        "ORD_UNPR": ord_unpr,
        "EXCG_ID_DVSN_CD": "KRX",
        "SLL_TYPE": "",
        "CNDT_PRIC": "",
    }


def buy(
    body: dict,
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> APIResponse:
    """
    매수 주문 body를 받아 order-cash API로 POST 요청을 보냅니다.
    주문 내용은 build_buy_order_body()로 생성한 dict를 넘깁니다.
    
    Args:
        body: 주문 body (build_buy_order_body() 반환값 또는 동일 형식의 dict)
        config: Config 인스턴스 (미입력 시 환경변수에서 로드, tr_id/실전·모의 구분용)
        client: HantooClient 인스턴스 (미입력 시 config로 생성)
        
    Returns:
        APIResponse (.success, .message, .data 등)
        
    Example:
        >>> body = build_buy_order_body("005930", 10, "limit", price=70000)
        >>> resp = buy(body)
    """
    cfg = config or Config.load()
    if client is None:
        client = HantooClient(cfg)
    tr_id = TR_ID_BUY_REAL if cfg.is_real else TR_ID_BUY_DEMO
    extra_headers = {"custtype": "P"}
    body_str = json.dumps(body, ensure_ascii=False)
    response = client.post(
        ENDPOINT_ORDER_CASH, tr_id, extra_headers=extra_headers, body_json_str=body_str
    )
    pdno = body.get("PDNO", "")
    quantity = body.get("ORD_QTY", "")
    if response.success:
        logger.info("매수 주문 성공: %s %s주 %s", pdno, quantity, response.message)
    else:
        logger.warning("매수 주문 실패: %s", response.message)
    return response


def inquire_daily_ccld(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sll_buy_dvsn_cd: str = "00",
    ccld_dvsn: str = "00",
    pdno: str = "",
    odno: str = "",
    translate_columns: bool = True,
    option_kor_cols: bool = False,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    주식 일별 주문체결 내역을 조회합니다.

    Args:
        start_date: 조회 시작일 (YYYYMMDD). 미입력 시 오늘.
        end_date:   조회 종료일 (YYYYMMDD). 미입력 시 오늘.
        sll_buy_dvsn_cd: 매도매수구분 (00:전체, 01:매도, 02:매수)
        ccld_dvsn: 체결구분 (00:전체, 01:체결, 02:미체결)
        pdno: 종목코드 (빈 문자열이면 전체)
        odno: 주문번호 (빈 문자열이면 전체)
        translate_columns: True면 한글 컬럼명 변환 (기존 호환용)
        option_kor_cols: True면 모든 컬럼명을 한국어 전문 용어로 변환
        config: Config 인스턴스
        client: HantooClient 인스턴스

    Returns:
        (체결내역 DataFrame, 요약 DataFrame)
    """
    cfg = config or Config.load()
    if client is None:
        client = HantooClient(cfg)

    tr_id = TR_ID_CCLD_REAL if cfg.is_real else TR_ID_CCLD_DEMO

    today = datetime.now().strftime("%Y%m%d")
    inqr_strt_dt = start_date or today
    inqr_end_dt = end_date or today

    params = {
        "CANO": cfg.account_no,
        "ACNT_PRDT_CD": cfg.account_product_code,
        "INQR_STRT_DT": inqr_strt_dt,
        "INQR_END_DT": inqr_end_dt,
        "SLL_BUY_DVSN_CD": sll_buy_dvsn_cd,
        "PDNO": pdno,
        "CCLD_DVSN": ccld_dvsn,
        "INQR_DVSN": "00",
        "INQR_DVSN_3": "00",
        "ORD_GNO_BRNO": "",
        "ODNO": odno,
        "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
        "EXCG_ID_DVSN_CD": "KRX",
    }

    all_orders: list[dict] = []
    summary_rows: list[dict] = []
    page = 0

    while True:
        resp = client.get(ENDPOINT_INQUIRE_DAILY_CCLD, tr_id, params=params)
        if not resp.success:
            logger.warning("체결 조회 실패: %s", resp.message)
            break

        rows = resp.output1
        if rows:
            all_orders.extend(rows)

        if page == 0:
            out2 = resp.data.get("output2")
            if out2:
                if isinstance(out2, list):
                    summary_rows.extend(out2)
                else:
                    summary_rows.append(out2)

        tr_cont = resp.data.get("tr_cont", "")
        if tr_cont in ("M", "F"):
            params["CTX_AREA_FK100"] = resp.ctx_area_fk100
            params["CTX_AREA_NK100"] = resp.ctx_area_nk100
            page += 1
            continue
        break

    df_orders = pd.DataFrame(all_orders) if all_orders else pd.DataFrame()
    df_summary = pd.DataFrame(summary_rows) if summary_rows else pd.DataFrame()

    if option_kor_cols or translate_columns:
        if not df_orders.empty:
            df_orders.rename(columns=MAPPING_KOR_COLUMNS, inplace=True)
        if not df_summary.empty:
            df_summary.rename(columns=MAPPING_KOR_COLUMNS, inplace=True)

    return df_orders, df_summary


def cancel_order(
    orgn_odno: str,
    krx_fwdg_ord_orgno: str = "",
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> APIResponse:
    """
    미체결 주문을 취소합니다.

    Args:
        orgn_odno: 원주문번호 (주문 응답의 ODNO)
        krx_fwdg_ord_orgno: 한국거래소전송주문조직번호
                            (주문 응답의 KRX_FWDG_ORD_ORGNO, 빈 문자열 허용)
        config: Config 인스턴스
        client: HantooClient 인스턴스

    Returns:
        APIResponse
    """
    cfg = config or Config.load()
    if client is None:
        client = HantooClient(cfg)

    tr_id = TR_ID_CANCEL_REAL if cfg.is_real else TR_ID_CANCEL_DEMO

    body = {
        "CANO": cfg.account_no,
        "ACNT_PRDT_CD": cfg.account_product_code,
        "KRX_FWDG_ORD_ORGNO": krx_fwdg_ord_orgno,
        "ORGN_ODNO": orgn_odno,
        "ORD_DVSN": "00",
        "RVSE_CNCL_DVSN_CD": "02",
        "ORD_QTY": "0",
        "ORD_UNPR": "0",
        "QTY_ALL_ORD_YN": "Y",
        "EXCG_ID_DVSN_CD": "KRX",
    }

    extra_headers = {"custtype": "P"}
    body_str = json.dumps(body, ensure_ascii=False)
    response = client.post(
        ENDPOINT_ORDER_RVSECNCL, tr_id, extra_headers=extra_headers, body_json_str=body_str
    )

    if response.success:
        logger.info("주문 취소 성공: %s %s", orgn_odno, response.message)
    else:
        logger.warning("주문 취소 실패: %s %s", orgn_odno, response.message)
    return response
