"""统一 LLM 客户端封装"""

from openai import OpenAI
from app.config import get_llm_config


def get_client() -> OpenAI:
    """返回当前模式的 OpenAI 客户端"""
    base_url, api_key, _model = get_llm_config()
    return OpenAI(base_url=base_url, api_key=api_key)


def get_model() -> str:
    """返回当前模式使用的模型名"""
    _base_url, _api_key, model = get_llm_config()
    return model
