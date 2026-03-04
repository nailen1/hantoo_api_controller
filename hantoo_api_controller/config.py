"""
환경변수 로드 및 설정 관리 모듈
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class Config:
    """한국투자증권 API 설정"""
    
    # API 인증 정보
    app_key: str
    app_secret: str
    
    # 계좌 정보
    account_no: str
    account_product_code: str
    
    # 환경 구분 (real: 실전, demo: 모의)
    env: str
    
    # API Base URL
    base_url: str
    
    @classmethod
    def load(cls, env_path: str = None) -> "Config":
        """
        환경변수에서 설정을 로드합니다.
        
        Args:
            env_path: .env 파일 경로 (기본값: 프로젝트 루트의 .env)
            
        Returns:
            Config 인스턴스
        """
        # .env 파일 로드
        if env_path:
            load_dotenv(env_path)
        else:
            # 프로젝트 루트에서 .env 찾기
            project_root = Path(__file__).parent.parent
            load_dotenv(project_root / ".env")
        
        # 환경 구분
        env = os.getenv("HANTOO_ENV", "demo")
        
        # Base URL 결정
        if env == "real":
            default_url = "https://openapi.koreainvestment.com:9443"
        else:
            default_url = "https://openapivts.koreainvestment.com:29443"
        
        base_url = os.getenv("HANTOO_BASE_URL", default_url)
        
        return cls(
            app_key=os.getenv("HANTOO_APP_KEY", ""),
            app_secret=os.getenv("HANTOO_APP_SECRET", ""),
            account_no=os.getenv("HANTOO_ACCOUNT_NO", ""),
            account_product_code=os.getenv("HANTOO_ACCOUNT_PRODUCT_CODE", "01"),
            env=env,
            base_url=base_url,
        )
    
    @property
    def is_real(self) -> bool:
        """실전투자 환경인지 확인"""
        return self.env == "real"
    
    @property
    def is_demo(self) -> bool:
        """모의투자 환경인지 확인"""
        return self.env == "demo"
    
    def validate(self) -> bool:
        """필수 설정값이 모두 있는지 검증"""
        required = [self.app_key, self.app_secret, self.account_no]
        return all(required)
