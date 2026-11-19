import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()  # .env 파일의 값을 환경변수로 불러옴


def make_client(prefix):
    """prefix(예: 'RESEARCH')에 해당하는 키/모델로 (client, model)을 만든다."""
    api_key = os.environ[f"{prefix}_API_KEY"]  # 에이전트별 API 키
    model = os.environ[f"{prefix}_MODEL"]  # 에이전트별 모델명
    # 503 등 일시적 오류(408·429·5xx) 시 최대 5번까지 점점 간격을 늘려 자동 재시도
    retry = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=5))
    return genai.Client(api_key=api_key, http_options=retry), model
