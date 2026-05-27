@echo off
echo 正在打包 MIMO-Responses 代理为 exe...
pip install pyinstaller -q
pyinstaller --onefile --name mimo-proxy --clean proxy.py
echo.
echo 打包完成！exe 文件位于: dist\mimo-proxy.exe
pause
