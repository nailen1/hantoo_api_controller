"""
한 번 토큰을 발급해 동일 클라이언트로 모든 API를 호출하는 세션 클래스.
토큰을 한 번만 발급하고 재사용하므로, 연속 호출 시 403(토큰 발급 거부)을 피할 수 있습니다.
"""

from typing import Literal, Optional, Tuple, Union

import pandas as pd

from .account import get_info_account
from .api_client import APIResponse, HantooClient
from .config import Config
from .order import build_buy_order_body, build_sell_order_body, buy, inquire_daily_ccld, sell
from .quote import current_price_value, get_current_price


class HantooSession:
    """
    한국투자증권 API 세션. 한 개의 클라이언트(토큰)로 모든 기능을 사용합니다.
    
    사용 예:
        session = HantooSession()
        holdings, summary = session.get_info_account()
        price = session.current_price_value("005930")
        body = session.build_sell_order_body("005930", 10, "limit", price=70000)
        resp = session.sell(body)
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Args:
            config: Config 인스턴스. None이면 환경변수(.env)에서 로드.
        """
        self._config = config or Config.load()
        self._client = HantooClient(self._config)

    @property
    def config(self) -> Config:
        """현재 설정."""
        return self._config

    @property
    def client(self) -> HantooClient:
        """내부 API 클라이언트(동일 토큰 유지). 다른 함수에 client= 로 넘겨 재사용 가능."""
        return self._client

    def get_info_account(
        self,
        translate_columns: bool = True,
        include_all_pages: bool = True,
        option_kor_cols: bool = False,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """계좌 잔고 조회. (holdings, summary) 반환."""
        return get_info_account(
            translate_columns=translate_columns,
            include_all_pages=include_all_pages,
            option_kor_cols=option_kor_cols,
            config=self._config,
            client=self._client,
        )

    def get_current_price(self, symbol: str) -> APIResponse:
        """종목 현재가 시세 전체 조회. .output 에 시세 dict."""
        return get_current_price(
            symbol,
            config=self._config,
            client=self._client,
        )

    def current_price_value(self, symbol: str) -> Optional[int]:
        """종목 현재가만 정수(원)로 반환. 실패 시 None."""
        return current_price_value(
            symbol,
            config=self._config,
            client=self._client,
        )

    def build_sell_order_body(
        self,
        symbol: str,
        quantity: int,
        order_type: Literal["limit", "market"] = "limit",
        price: Optional[Union[int, float]] = None,
    ) -> dict:
        """매도 주문 body 생성. POST 하지 않음."""
        return build_sell_order_body(
            symbol, quantity, order_type, price=price, config=self._config
        )

    def build_buy_order_body(
        self,
        symbol: str,
        quantity: int,
        order_type: Literal["limit", "market"] = "limit",
        price: Optional[Union[int, float]] = None,
    ) -> dict:
        """매수 주문 body 생성. POST 하지 않음."""
        return build_buy_order_body(
            symbol, quantity, order_type, price=price, config=self._config
        )

    def build_buy_order_body_by_amount(
        self,
        symbol: str,
        amount: int,
        order_type: Literal["limit", "market"] = "limit",
        price: Optional[Union[int, float]] = None,
    ) -> dict:
        """
        총 주문금액(원) 기준으로 매수 가능 수량을 환산하여 매수 주문 body를 생성합니다.

        현재가(또는 지정가)로 amount를 나눠 매수 가능한 최대 정수 수량을 계산합니다.
        수량이 0이면 ValueError를 발생시킵니다.

        Args:
            symbol: 종목코드 6자리
            amount: 총 주문금액 (원)
            order_type: "limit" 지정가 / "market" 시장가
            price: 지정가 (미입력 시 현재가 자동 조회)

        Returns:
            매수 주문 body dict (quantity가 환산된 상태)
        """
        if price is None:
            price = self.current_price_value(symbol)
            if price is None:
                raise ValueError(f"종목 {symbol}의 현재가를 조회할 수 없습니다")

        quantity = int(amount // price)
        if quantity <= 0:
            raise ValueError(
                f"주문금액 {amount:,}원으로 {symbol}(단가 {int(price):,}원)을 "
                f"1주도 매수할 수 없습니다"
            )

        return build_buy_order_body(
            symbol, quantity, order_type, price=price, config=self._config
        )

    def sell(self, body: dict) -> APIResponse:
        """매도 주문 전송."""
        return sell(body, config=self._config, client=self._client)

    def buy(self, body: dict) -> APIResponse:
        """매수 주문 전송."""
        return buy(body, config=self._config, client=self._client)

    def inquire_daily_ccld(
        self,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sll_buy_dvsn_cd: str = "00",
        ccld_dvsn: str = "00",
        pdno: str = "",
        odno: str = "",
        translate_columns: bool = True,
        option_kor_cols: bool = False,
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

        Returns:
            (체결내역 DataFrame, 요약 DataFrame)
        """
        return inquire_daily_ccld(
            start_date=start_date,
            end_date=end_date,
            sll_buy_dvsn_cd=sll_buy_dvsn_cd,
            ccld_dvsn=ccld_dvsn,
            pdno=pdno,
            odno=odno,
            translate_columns=translate_columns,
            option_kor_cols=option_kor_cols,
            config=self._config,
            client=self._client,
        )
