@echo off
chcp 65001 >nul
REM Set your DeepSeek API Key for online mode
REM set OPENAI_API_KEY=your_key_here
echo ===================================
echo   InkReel - AI Novel to Script Tool
echo ===================================
echo.
echo   Online:  DeepSeek API (default)
echo   Offline: Ollama local model
echo   Switch:  click toggle in web UI
echo.
echo   Open http://localhost:8766
echo ===================================
echo.
D:\Python3.9\python.exe backend\server.py
pause
