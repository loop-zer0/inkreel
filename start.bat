@echo off
REM 请设置你的 DeepSeek API Key（在线模式需要）
REM set OPENAI_API_KEY=your_key_here
echo ===================================
echo   InkReel — AI 小说转剧本工具 (Ink → Reel)
echo ===================================
echo.
echo   在线模式: DeepSeek API（默认）
echo   离线模式: Ollama 本地模型
echo   切换方法: 界面内点击开关
echo.
echo   打开 http://localhost:8766
echo ===================================
echo.
D:\Python3.9\python.exe backend\server.py
pause
