@echo off
chcp 65001 >nul
echo MIMO-Responses 代理启动脚本
echo ============================
echo.
echo 使用方法:
echo   run.bat [API_KEY] [选项]
echo.
echo 示例:
echo   run.bat sk-xxxxx                    (按量付费)
echo   run.bat tp-xxxxx                    (Token Plan)
echo   run.bat sk-xxxxx --write-codex      (写入 Codex 配置)
echo   run.bat sk-xxxxx --no-thinking      (禁用思考模式)
echo.
echo cc-switch 集成:
echo   1. 启动代理后，在 cc-switch 中添加自定义 provider
echo   2. Base URL 设为: http://127.0.0.1:8888/v1
echo   3. API Key 设为你的 MIMO API Key
echo.

if "%~1"=="" (
    echo 请提供 API Key 作为参数
    echo.
    echo 按量付费: 从 https://platform.xiaomimimo.com/#/console/api-keys 获取 (sk-xxxxx)
    echo Token Plan: 从 https://platform.xiaomimimo.com/#/console/plan-manage 获取 (tp-xxxxx)
    pause
    exit /b 1
)

python proxy.py --api-key %*
pause
