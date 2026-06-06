"""InkReel 启动入口 — python run.py"""
import uvicorn
from app.config import HOST, PORT, LLM_MODE, get_llm_config

if __name__ == "__main__":
    base_url, api_key, model = get_llm_config()
    print(f"""
  ==================================
    InkReel — AI 小说转剧本工具
  ==================================
    LLM 模式: {LLM_MODE}
    模型:     {model}
    地址:     http://{HOST}:{PORT}
  ==================================
""")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
