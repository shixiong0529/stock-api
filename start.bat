@echo off
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=
set http_proxy=
set https_proxy=
set all_proxy=
set NO_PROXY=*
set no_proxy=*

:restart
cd /d C:\Users\Administrator\.openclaw\workspace-stock\stock-api
echo [%date% %time%] Starting stock-api on port 7070...
python -m uvicorn main:app --host 127.0.0.1 --port 7070 --workers 1
echo [%date% %time%] Service exited. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto restart
