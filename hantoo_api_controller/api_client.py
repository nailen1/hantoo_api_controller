"""
한국투자증권 API 호출 클라이언트
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional, Union

import requests

from .auth import HantooAuth
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """API 응답 래퍼 클래스"""
    
    success: bool
    status_code: int
    data: dict
    message: str = ""
    
    @property
    def output1(self) -> list:
        """output1 데이터 반환"""
        return self.data.get("output1", [])
    
    @property
    def output2(self) -> list:
        """output2 데이터 반환"""
        return self.data.get("output2", [])
    
    @property
    def output(self) -> Any:
        """단일 output 데이터 반환"""
        return self.data.get("output", self.data)
    
    @property
    def rt_cd(self) -> str:
        """응답 코드 (0: 성공)"""
        return self.data.get("rt_cd", "")
    
    @property
    def msg1(self) -> str:
        """응답 메시지"""
        return self.data.get("msg1", "")
    
    # 연속조회 관련
    @property
    def ctx_area_fk100(self) -> str:
        return self.data.get("ctx_area_fk100", "")
    
    @property
    def ctx_area_nk100(self) -> str:
        return self.data.get("ctx_area_nk100", "")


ENDPOINT_HASHKEY = "/uapi/hashkey"


class HantooClient:
    """한국투자증권 API 클라이언트"""
    
    # API 호출 간 최소 대기 시간 (초)
    MIN_REQUEST_INTERVAL = 0.1
    
    def __init__(self, config: Config = None):
        """
        Args:
            config: Config 인스턴스 (기본값: 환경변수에서 자동 로드)
        """
        self.config = config or Config.load()
        self.auth = HantooAuth(self.config)
        self._last_request_time: float = 0
    
    def get_hashkey(self, body: Union[dict, str]) -> Optional[str]:
        """
        POST 주문 등에 필요한 hashkey를 발급받습니다.
        주문에 보낼 body와 **동일한 문자열**을 보내야 합니다. dict면 JSON 문자열로 직렬화합니다.
        
        Args:
            body: 주문 요청 body (dict 또는 주문 API에 보낼 그대로의 JSON 문자열)
        Returns:
            HASH 문자열. 실패 시 None.
        """
        self._smart_sleep()
        url = f"{self.config.base_url}{ENDPOINT_HASHKEY}"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "appKey": self.config.app_key,
            "appSecret": self.config.app_secret,
        }
        if isinstance(body, dict):
            body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
        else:
            body_bytes = body.encode("utf-8") if isinstance(body, str) else body
        try:
            response = requests.post(url, headers=headers, data=body_bytes)
            self._last_request_time = time.time()
            if response.status_code == 200:
                data = response.json()
                if isinstance(data.get("body"), dict):
                    h = data["body"].get("HASH")
                else:
                    h = data.get("HASH")
                if h:
                    return h
            logger.warning("hashkey 발급 실패: %s - %s", response.status_code, response.text)
            return None
        except requests.RequestException as e:
            logger.warning("hashkey 요청 실패: %s", str(e))
            return None
    
    def _smart_sleep(self) -> None:
        """API 호출 간 적절한 대기"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
    
    def get(
        self,
        endpoint: str,
        tr_id: str,
        params: dict = None,
        tr_cont: str = "",
    ) -> APIResponse:
        """
        GET 요청을 수행합니다.
        
        Args:
            endpoint: API 엔드포인트 (예: /uapi/domestic-stock/v1/trading/inquire-balance)
            tr_id: 거래 ID
            params: 쿼리 파라미터
            tr_cont: 연속거래 여부
            
        Returns:
            APIResponse 인스턴스
        """
        self._smart_sleep()
        
        url = f"{self.config.base_url}{endpoint}"
        headers = self.auth.get_auth_headers(tr_id)
        
        if tr_cont:
            headers["tr_cont"] = tr_cont
        
        try:
            response = requests.get(url, headers=headers, params=params)
            self._last_request_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                success = data.get("rt_cd") == "0"
                return APIResponse(
                    success=success,
                    status_code=response.status_code,
                    data=data,
                    message=data.get("msg1", ""),
                )
            else:
                logger.error("API 호출 실패: %s - %s", response.status_code, response.text)
                return APIResponse(
                    success=False,
                    status_code=response.status_code,
                    data={},
                    message=response.text,
                )
                
        except requests.RequestException as e:
            logger.error("API 요청 실패: %s", str(e))
            return APIResponse(
                success=False,
                status_code=0,
                data={},
                message=str(e),
            )
    
    def post(
        self,
        endpoint: str,
        tr_id: str,
        data: dict = None,
        extra_headers: dict = None,
        body_json_str: Optional[str] = None,
    ) -> APIResponse:
        """
        POST 요청을 수행합니다.
        
        Args:
            endpoint: API 엔드포인트
            tr_id: 거래 ID
            data: 요청 바디 데이터 (body_json_str 없을 때 사용)
            extra_headers: 추가 헤더 (예: 주문 시 custtype, hashkey)
            body_json_str: 주문 등 hashkey와 동일한 body를 쓸 때, 직렬화된 JSON 문자열
        """
        self._smart_sleep()
        url = f"{self.config.base_url}{endpoint}"
        headers = self.auth.get_auth_headers(tr_id)
        if extra_headers:
            headers.update(extra_headers)
        if body_json_str is not None:
            body_bytes = body_json_str.encode("utf-8")
        else:
            body_bytes = None
        try:
            if body_bytes is not None:
                response = requests.post(url, headers=headers, data=body_bytes)
            else:
                response = requests.post(url, headers=headers, json=data)
            self._last_request_time = time.time()
            if response.status_code == 200:
                resp_data = response.json()
                success = resp_data.get("rt_cd") == "0"
                return APIResponse(
                    success=success,
                    status_code=response.status_code,
                    data=resp_data,
                    message=resp_data.get("msg1", ""),
                )
            else:
                logger.error("API 호출 실패: %s - %s", response.status_code, response.text)
                try:
                    err_data = response.json()
                    msg = err_data.get("msg1", response.text)
                except Exception:
                    err_data = {}
                    msg = response.text
                return APIResponse(
                    success=False,
                    status_code=response.status_code,
                    data=err_data,
                    message=msg,
                )
        except requests.RequestException as e:
            logger.error("API 요청 실패: %s", str(e))
            return APIResponse(
                success=False,
                status_code=0,
                data={},
                message=str(e),
            )
