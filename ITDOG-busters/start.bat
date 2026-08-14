@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [%date% %time%] 開始執行 ITDOG 批量測試
python run_all.py
echo [%date% %time%] 執行完成
