@echo off
title ShopEase Backend Server (FastAPI)
cd /d "%~dp0"
echo ========================================================
echo   KHOI DONG SHOPEASE BACKEND SERVER
echo   API Docs: http://127.0.0.1:8000/docs
echo ========================================================
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
