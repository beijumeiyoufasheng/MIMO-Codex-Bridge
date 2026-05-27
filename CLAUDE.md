# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**MIMO Codex Bridge (MIMO Codex 桥接器)** - 轻量级协议转换代理，将 OpenAI Responses API 格式转换为 Chat Completions 格式，使 Codex 能够使用小米 MIMO 模型。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行代理（按量付费）
python proxy.py --api-key sk-xxxxx

# 运行代理（Token Plan）
python proxy.py --api-key tp-xxxxx

# 运行代理并自动写入 Codex 配置
python proxy.py --api-key sk-xxxxx --write-codex

# 打包为 exe
build.bat

# 运行测试
python test_proxy.py
```

## 架构说明

单文件架构，核心逻辑在 `proxy.py`：

- **协议转换层**：`responses_to_chat_completions()` 将 Responses API 请求转为 Chat Completions 格式，`chat_response_to_responses()` 处理反向转换
- **流式处理**：`stream_chat_completions()` 处理 SSE 流式响应，转换事件格式
- **MIMO 特性支持**：处理 `reasoning_content`（思考模式）和 `tool_calls` 字段
- **Tools 转换**：`_convert_tools()` 处理 Responses API 和 Chat Completions 两种 tools 格式
- **计费模式自动检测**：根据 API Key 前缀（`sk-` / `tp-`）自动选择后端端点
- **安全认证**：`/config` 端点支持 Bearer Token 认证（通过 `--admin-token` 参数）
- **cc-switch 集成**：通过 `/config` API 和 `--write-codex` 参数支持配置管理

## 关键配置

- MIMO 按量付费端点：`https://api.xiaomimimo.com/v1`
- MIMO Token Plan 端点：`https://token-plan-cn.xiaomimimo.com/v1`
- 代理默认监听：`127.0.0.1:8888`
- Codex 配置目录：`~/.codex/`（auth.json + config.toml）

## API 端点

- `POST /v1/responses` - Responses API 主端点
- `GET /v1/models` - 模型列表透传
- `GET/POST /config` - 配置管理（用于 cc-switch 集成）
- `GET /health` - 健康检查
