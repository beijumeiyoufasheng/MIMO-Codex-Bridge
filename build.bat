@echo off
echo Building MIMO Codex Bridge...
pip install pyinstaller -q
pyinstaller --onefile --name mimo-proxy --clean proxy.py
echo.
echo Build complete! exe file: dist\mimo-proxy.exe
pause
