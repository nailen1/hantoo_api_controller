"""
계좌 관련 API 함수 모듈
"""

import logging
from typing import Optional, Tuple

import pandas as pd

from .api_client import HantooClient
from .config import Config
from .consts import MAPPING_KOR_COLUMNS

logger = logging.getLogger(__name__)


def get_info_account(
    translate_columns: bool = True,
    include_all_pages: bool = True,
    option_kor_cols: bool = False,
    *,
    config: Optional[Config] = None,
    client: Optional[HantooClient] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    계좌 잔고 정보를 조회합니다.
    
    환경변수에서 계좌 정보를 자동으로 로드하여 잔고를 조회합니다.
    client를 넘기면 해당 클라이언트(동일 토큰)를 재사용합니다.
    
    Args:
        translate_columns: True면 컬럼명을 한글로 변환 (기존 호환용)
        include_all_pages: True면 연속조회로 모든 데이터 가져오기
        option_kor_cols: True면 모든 컬럼명을 한국어 전문 용어로 변환
                         (translate_columns보다 우선 적용)
        config: Config 인스턴스 (미입력 시 환경변수에서 로드)
        client: HantooClient 인스턴스 (미입력 시 config로 생성, 넘기면 토큰 재사용)
        
    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 
            - output1: 보유종목 상세 정보 (종목별 보유수량, 평가금액 등)
            - output2: 계좌 요약 정보 (총평가금액, 예수금 등)
            
    Example:
        >>> holdings, summary = get_info_account()
        >>> holdings, summary = get_info_account(option_kor_cols=True)
    """
    if client is not None:
        config = client.config
    else:
        config = config or Config.load()
        client = HantooClient(config)
    
    # 환경에 따른 TR_ID 설정
    tr_id = "TTTC8434R" if config.is_real else "VTTC8434R"
    
    endpoint = "/uapi/domestic-stock/v1/trading/inquire-balance"
    
    all_holdings = []
    all_summary = []
    
    # 연속조회 키
    fk100 = ""
    nk100 = ""
    tr_cont = ""
    
    max_pages = 10 if include_all_pages else 1
    
    for page in range(max_pages):
        params = {
            "CANO": config.account_no,
            "ACNT_PRDT_CD": config.account_product_code,
            "AFHR_FLPR_YN": "N",  # 시간외단일가 여부
            "OFL_YN": "",
            "INQR_DVSN": "02",    # 조회구분 (02: 종목별)
            "UNPR_DVSN": "01",    # 단가구분
            "FUND_STTL_ICLD_YN": "N",  # 펀드결제분 포함 여부
            "FNCG_AMT_AUTO_RDPT_YN": "N",  # 융자금액 자동상환 여부
            "PRCS_DVSN": "00",    # 처리구분 (00: 전일매매포함)
            "CTX_AREA_FK100": fk100,
            "CTX_AREA_NK100": nk100,
        }
        
        response = client.get(endpoint, tr_id, params, tr_cont)
        
        if not response.success:
            logger.error("계좌 조회 실패: %s", response.message)
            break
        
        # 데이터 수집 (output2 계좌요약은 첫 페이지만 사용, 페이지마다 동일함)
        if response.output1:
            all_holdings.extend(response.output1)
        if response.output2 and page == 0:
            all_summary.extend(response.output2)
        
        # 연속조회 확인
        fk100 = response.ctx_area_fk100
        nk100 = response.ctx_area_nk100
        
        # 헤더에서 tr_cont 확인 (M 또는 F면 다음 페이지 있음)
        # 더 이상 데이터가 없으면 종료
        if not fk100 and not nk100:
            break
        
        tr_cont = "N"
        logger.info("연속조회 %d 페이지...", page + 2)
    
    # DataFrame 생성
    df_holdings = pd.DataFrame(all_holdings)
    df_summary = pd.DataFrame(all_summary)
    
    if option_kor_cols or translate_columns:
        df_holdings = df_holdings.rename(columns=MAPPING_KOR_COLUMNS)
        df_summary = df_summary.rename(columns=MAPPING_KOR_COLUMNS)
    
    logger.info("계좌 조회 완료 - 보유종목 %d건", len(df_holdings))
    
    return df_holdings, df_summary
