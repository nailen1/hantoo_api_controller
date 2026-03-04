"""
한국투자증권 API 인증 토큰 관리 모듈

토큰을 프로젝트 루트의 .cache/token_cache.json 에 캐시하여,
커널 재시작이나 새 세션 생성 시에도 유효한 토큰을 재사용합니다.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from .config import Config

logger = logging.getLogger(__name__)

_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
_CACHE_DIR_NAME = ".cache"
_CACHE_FILE_NAME = "token_cache.json"


def _get_cache_path() -> Path:
    project_root = Path(__file__).parent.parent
    return project_root / _CACHE_DIR_NAME / _CACHE_FILE_NAME


def _app_key_hash(app_key: str) -> str:
    return hashlib.sha256(app_key.encode()).hexdigest()[:16]


class HantooAuth:
    """한국투자증권 API 인증 관리 클래스"""

    TOKEN_URL = "/oauth2/tokenP"
    REFRESH_MARGIN = timedelta(minutes=30)

    def __init__(self, config: Config = None):
        """
        Args:
            config: Config 인스턴스 (기본값: 환경변수에서 자동 로드)
        """
        self.config = config or Config.load()
        self._access_token: Optional[str] = None
        self._token_expired_at: Optional[datetime] = None
        self._load_cache()

    @property
    def access_token(self) -> str:
        """
        액세스 토큰을 반환합니다.
        토큰이 없거나 만료 임박 시 자동으로 재발급합니다.
        """
        if self._is_token_expired():
            self._issue_token()
        return self._access_token

    def _is_token_expired(self) -> bool:
        if not self._access_token or not self._token_expired_at:
            return True
        return datetime.now() >= self._token_expired_at - self.REFRESH_MARGIN

    # ── 캐시 저장/로드 ──

    def _load_cache(self) -> None:
        """캐시 파일에서 유효한 토큰을 로드합니다."""
        cache_path = _get_cache_path()
        if not cache_path.exists():
            return

        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.debug("토큰 캐시 파일 읽기 실패, 무시합니다")
            return

        if data.get("app_key_hash") != _app_key_hash(self.config.app_key):
            logger.debug("캐시의 app_key_hash 불일치, 무시합니다")
            return

        try:
            expires_at = datetime.strptime(data["expires_at"], _DATETIME_FMT)
        except (KeyError, ValueError):
            return

        if datetime.now() >= expires_at - self.REFRESH_MARGIN:
            logger.debug("캐시 토큰 만료 임박, 무시합니다")
            return

        self._access_token = data["access_token"]
        self._token_expired_at = expires_at
        logger.info(
            "캐시에서 토큰 로드 성공 (만료: %s)",
            expires_at.strftime(_DATETIME_FMT),
        )

    def _save_cache(self) -> None:
        """현재 토큰을 캐시 파일에 저장합니다."""
        cache_path = _get_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "access_token": self._access_token,
            "issued_at": (
                self._token_expired_at - timedelta(hours=24)
            ).strftime(_DATETIME_FMT),
            "expires_at": self._token_expired_at.strftime(_DATETIME_FMT),
            "app_key_hash": _app_key_hash(self.config.app_key),
            "env": self.config.env,
        }
        cache_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.debug("토큰 캐시 저장 완료: %s", cache_path)

    # ── 토큰 발급 ──

    def _issue_token(self) -> None:
        """OAuth 접근 토큰을 발급하고 캐시에 저장합니다."""
        url = f"{self.config.base_url}{self.TOKEN_URL}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "charset": "UTF-8",
        }

        data = {
            "grant_type": "client_credentials",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
        }

        try:
            response = requests.post(url, data=json.dumps(data), headers=headers)

            if response.status_code == 200:
                result = response.json()
                self._access_token = result.get("access_token")

                expires_in = result.get("expires_in", 86400)
                self._token_expired_at = datetime.now() + timedelta(seconds=expires_in)

                logger.info("토큰 발급 성공 (만료: %s)", self._token_expired_at)
                self._save_cache()
            else:
                logger.error(
                    "토큰 발급 실패: %s - %s (base_url=%s)",
                    response.status_code,
                    response.text,
                    self.config.base_url,
                )
                msg = f"토큰 발급 실패: {response.status_code}. 응답: {response.text}"
                if response.status_code == 403:
                    msg += (
                        " 403일 때: 모의투자(openapivts)에는 모의용 앱키/시크릿, "
                        "실전(openapi)에는 실전용 앱키/시크릿을 사용해야 합니다. "
                        "포털에서 앱 승인·IP 제한도 확인하세요."
                    )
                raise Exception(msg)

        except requests.RequestException as e:
            logger.error("토큰 발급 요청 실패: %s", str(e))
            raise

    def get_auth_headers(self, tr_id: str) -> dict:
        """
        API 호출에 필요한 인증 헤더를 반환합니다.

        Args:
            tr_id: 거래 ID

        Returns:
            인증 헤더 딕셔너리
        """
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
            "tr_id": tr_id,
        }
