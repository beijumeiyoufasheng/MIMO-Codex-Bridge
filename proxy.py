#!/usr/bin/env python3
"""MIMO-to-Responses API 协议转换代理

将 OpenAI Responses API 格式转换为 Chat Completions 格式，
使 Codex 能够使用小米 MIMO 模型。

支持两种计费模式：
- 按量付费：API Key 格式 sk-xxxxx
- Token Plan：API Key 格式 tp-xxxxx

支持 cc-switch 集成管理多个账号站点。

MIMO API 文档: https://platform.xiaomimimo.com/docs/zh-CN/welcome
cc-switch: https://github.com/farion1231/cc-switch
"""

import json
import uuid
import time
import argparse
import logging
import secrets
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mimo-proxy")

# TOML 解析（兼容 Python 3.11+）
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None
        logger.warning("tomllib 不可用，TOML 解析将使用简单模式")


# MIMO API 端点配置
MIMO_ENDPOINTS = {
    "pay-as-you-go": "https://api.xiaomimimo.com/v1",
    "token-plan": "https://token-plan-cn.xiaomimimo.com/v1",
}

# FastAPI 应用
app = FastAPI(title="MIMO Codex Bridge")


# Pydantic 模型
class ResponsesRequest(BaseModel):
    """Responses API 请求模型"""
    model: str = "mimo-v2.5-pro"
    input: str | list[Any] = ""
    instructions: Optional[str] = None
    stream: bool = False
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    top_p: Optional[float] = None
    tools: Optional[list[dict]] = None
    tool_choice: Optional[str | dict] = None
    api_key: Optional[str] = None


class ConfigUpdate(BaseModel):
    """配置更新请求模型"""
    api_key: Optional[str] = None
    backend_url: Optional[str] = None
    enable_thinking: Optional[bool] = None
    write_codex: bool = False
    model: str = "mimo-v2.5-pro"


class ProxyConfig:
    """代理配置（线程安全）"""

    def __init__(self):
        self.backend_url: str = ""
        self.api_key: str = ""
        self.port: int = 8888
        self.host: str = "127.0.0.1"
        self.enable_thinking: bool = True
        self.codex_config_dir: str = ""
        self.admin_token: str = ""  # 配置管理认证 token

    def get_codex_config_dir(self) -> Path:
        if self.codex_config_dir:
            return Path(self.codex_config_dir)
        return Path.home() / ".codex"


config = ProxyConfig()


# 认证
security = HTTPBearer(auto_error=False)


def detect_api_type(api_key: str) -> str:
    """根据 API Key 前缀自动检测计费类型"""
    if api_key.startswith("tp-"):
        return "token-plan"
    return "pay-as-you-go"


def get_backend_url(api_key: str, custom_url: str = "") -> str:
    """获取后端 URL"""
    if custom_url:
        return custom_url
    api_type = detect_api_type(api_key)
    return MIMO_ENDPOINTS[api_type]


def read_codex_config() -> dict:
    """读取当前 Codex 配置"""
    codex_dir = config.get_codex_config_dir()
    result = {"api_key": "", "base_url": "", "model": ""}

    # 读取 auth.json
    auth_file = codex_dir / "auth.json"
    if auth_file.exists():
        try:
            with open(auth_file, "r", encoding="utf-8") as f:
                auth = json.load(f)
                result["api_key"] = auth.get("OPENAI_API_KEY", "")
        except Exception as e:
            logger.warning(f"读取 auth.json 失败: {e}")

    # 读取 config.toml
    config_file = codex_dir / "config.toml"
    if config_file.exists():
        try:
            if tomllib:
                with open(config_file, "rb") as f:
                    toml_data = tomllib.load(f)
                    result["base_url"] = toml_data.get("base_url", "")
                    result["model"] = toml_data.get("model", "")
            else:
                # 简单解析 fallback
                with open(config_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or "=" not in line:
                            continue
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key == "base_url":
                            result["base_url"] = value
                        elif key == "model":
                            result["model"] = value
        except Exception as e:
            logger.warning(f"读取 config.toml 失败: {e}")

    return result


def write_codex_config(api_key: str, base_url: str, model: str = "mimo-v2.5-pro"):
    """写入 Codex 配置（用于 cc-switch 集成）"""
    codex_dir = config.get_codex_config_dir()
    codex_dir.mkdir(parents=True, exist_ok=True)

    # 写入 auth.json
    auth_file = codex_dir / "auth.json"
    with open(auth_file, "w", encoding="utf-8") as f:
        json.dump({"OPENAI_API_KEY": api_key}, f, indent=2)

    # 写入 config.toml
    config_file = codex_dir / "config.toml"
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(f'base_url = "{base_url}"\n')
        f.write(f'model = "{model}"\n')

    logger.info(f"已写入 Codex 配置到 {codex_dir}")


def responses_to_chat_completions(body: dict) -> dict:
    """将 Responses API 请求转换为 Chat Completions 格式"""
    messages = []
    model = body.get("model", "mimo-v2.5-pro")

    # 处理 input 字段
    inp = body.get("input", "")
    if isinstance(inp, str):
        messages.append({"role": "user", "content": inp})
    elif isinstance(inp, list):
        for item in inp:
            if isinstance(item, str):
                messages.append({"role": "user", "content": item})
            elif isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", "")

                # 处理 Responses API 的 content 数组格式
                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") in ("output_text", "input_text"):
                                text_parts.append(part.get("text", ""))
                        elif isinstance(part, str):
                            text_parts.append(part)
                    content = "\n".join(text_parts)

                msg = {"role": role, "content": content}

                # 保留 reasoning_content（MIMO 思考模式必需）
                if "reasoning_content" in item:
                    msg["reasoning_content"] = item["reasoning_content"]

                # 保留 tool_calls
                if "tool_calls" in item:
                    msg["tool_calls"] = item["tool_calls"]

                messages.append(msg)

    # 处理 instructions（系统提示词）
    instructions = body.get("instructions")
    if instructions:
        messages.insert(0, {"role": "system", "content": instructions})

    # 构建 Chat Completions 请求
    result = {
        "model": model,
        "messages": messages,
        "stream": body.get("stream", False),
    }

    # 传递思考模式配置
    if config.enable_thinking:
        result["thinking"] = {"type": "enabled", "budget_tokens": 10240}

    # 传递其他参数
    if "temperature" in body and body["temperature"] is not None:
        result["temperature"] = body["temperature"]
    if "max_output_tokens" in body and body["max_output_tokens"] is not None:
        result["max_tokens"] = body["max_output_tokens"]
    if "top_p" in body and body["top_p"] is not None:
        result["top_p"] = body["top_p"]

    # 转换 tools 参数
    if "tools" in body and body["tools"]:
        result["tools"] = _convert_tools(body["tools"])
    if "tool_choice" in body and body["tool_choice"] is not None:
        result["tool_choice"] = body["tool_choice"]

    return result


def _convert_tools(tools: list[dict]) -> list[dict]:
    """转换 Responses API tools 格式到 Chat Completions 格式"""
    converted = []
    for tool in tools:
        if "function" in tool and isinstance(tool["function"], dict):
            # 已经是 Chat Completions 格式：{type: "function", function: {...}}
            converted.append(tool)
        elif tool.get("type") == "function" and "name" in tool:
            # Responses API 格式：{type: "function", name: "...", ...}
            func = {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                }
            }
            converted.append(func)
        else:
            # 尝试兼容其他格式
            converted.append(tool)
    return converted


def chat_response_to_responses(resp: dict) -> dict:
    """将 Chat Completions 非流式响应转换为 Responses API 格式"""
    response_id = f"resp_{uuid.uuid4().hex[:24]}"

    content = ""
    reasoning_content = ""
    tool_calls = []

    if resp.get("choices"):
        message = resp["choices"][0].get("message", {})
        content = message.get("content", "") or ""
        reasoning_content = message.get("reasoning_content", "") or ""
        tool_calls = message.get("tool_calls", []) or []

    # 构建输出内容
    output_content = []
    if reasoning_content:
        output_content.append({
            "type": "reasoning_text",
            "text": reasoning_content,
        })
    if content:
        output_content.append({
            "type": "output_text",
            "text": content,
            "annotations": [],
        })

    # 构建输出项
    output_item = {
        "type": "message",
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "role": "assistant",
        "status": "completed",
        "content": output_content,
    }

    # 处理 tool_calls
    if tool_calls:
        for tc in tool_calls:
            output_item["content"].append({
                "type": "tool_call",
                "id": tc.get("id", ""),
                "function": {
                    "name": tc.get("function", {}).get("name", ""),
                    "arguments": tc.get("function", {}).get("arguments", ""),
                },
            })

    return {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": resp.get("model", "mimo"),
        "output": [output_item],
        "usage": resp.get("usage", {}),
    }


async def stream_chat_completions(
    client: httpx.AsyncClient, url: str, headers: dict, payload: dict
) -> AsyncIterator[str]:
    """流式调用 Chat Completions 并转换为 Responses API 事件流"""
    response_id = f"resp_{uuid.uuid4().hex[:24]}"
    message_id = f"msg_{uuid.uuid4().hex[:24]}"

    # 发送 response.created 事件
    yield f"data: {json.dumps({'type': 'response.created', 'response': {'id': response_id, 'object': 'response', 'created_at': int(time.time()), 'status': 'in_progress', 'model': payload.get('model', 'mimo'), 'output': []}}, ensure_ascii=False)}\n\n"

    # 发送 response.in_progress 事件
    yield f"data: {json.dumps({'type': 'response.in_progress'}, ensure_ascii=False)}\n\n"

    # 发送 output_item.added 事件
    yield f"data: {json.dumps({'type': 'response.output_item.added', 'output_index': 0, 'item': {'type': 'message', 'id': message_id, 'role': 'assistant', 'status': 'in_progress', 'content': []}}, ensure_ascii=False)}\n\n"

    collected_content = []
    collected_reasoning = []
    has_reasoning = False
    has_content = False
    content_index = 0

    try:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            # 检查响应状态
            if response.status_code != 200:
                error_body = await response.aread()
                error_msg = error_body.decode("utf-8", errors="replace")
                logger.error(f"后端返回错误 {response.status_code}: {error_msg}")
                yield f"data: {json.dumps({'type': 'response.error', 'error': {'type': 'backend_error', 'code': response.status_code, 'message': error_msg}}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data = line[6:]
                if data.strip() == "[DONE]":
                    break

                try:
                    chunk = json.loads(data)
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    finish_reason = choices[0].get("finish_reason")

                    # 处理 reasoning_content（MIMO 思考模式）
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        if not has_reasoning:
                            has_reasoning = True
                            yield f"data: {json.dumps({'type': 'response.content_part.added', 'output_index': 0, 'content_index': 0, 'part': {'type': 'reasoning_text', 'text': ''}}, ensure_ascii=False)}\n\n"

                        collected_reasoning.append(reasoning)
                        yield f"data: {json.dumps({'type': 'response.reasoning_text.delta', 'output_index': 0, 'content_index': 0, 'delta': reasoning}, ensure_ascii=False)}\n\n"

                    # 处理 content
                    content = delta.get("content")
                    if content:
                        if not has_content and has_reasoning:
                            yield f"data: {json.dumps({'type': 'response.content_part.done', 'output_index': 0, 'content_index': 0, 'part': {'type': 'reasoning_text', 'text': ''.join(collected_reasoning)}}, ensure_ascii=False)}\n\n"
                            content_index = 1
                            yield f"data: {json.dumps({'type': 'response.content_part.added', 'output_index': 0, 'content_index': content_index, 'part': {'type': 'output_text', 'text': '', 'annotations': []}}, ensure_ascii=False)}\n\n"
                        elif not has_content:
                            yield f"data: {json.dumps({'type': 'response.content_part.added', 'output_index': 0, 'content_index': 0, 'part': {'type': 'output_text', 'text': '', 'annotations': []}}, ensure_ascii=False)}\n\n"

                        has_content = True
                        collected_content.append(content)
                        yield f"data: {json.dumps({'type': 'response.output_text.delta', 'output_index': 0, 'content_index': content_index, 'delta': content}, ensure_ascii=False)}\n\n"

                    # 处理完成
                    if finish_reason:
                        if has_content:
                            yield f"data: {json.dumps({'type': 'response.content_part.done', 'output_index': 0, 'content_index': content_index, 'part': {'type': 'output_text', 'text': ''.join(collected_content), 'annotations': []}}, ensure_ascii=False)}\n\n"
                        elif has_reasoning:
                            yield f"data: {json.dumps({'type': 'response.content_part.done', 'output_index': 0, 'content_index': 0, 'part': {'type': 'reasoning_text', 'text': ''.join(collected_reasoning)}}, ensure_ascii=False)}\n\n"

                        yield f"data: {json.dumps({'type': 'response.output_item.done', 'output_index': 0, 'item': {'type': 'message', 'id': message_id, 'role': 'assistant', 'status': 'completed', 'content': []}}, ensure_ascii=False)}\n\n"

                except json.JSONDecodeError:
                    continue

    except httpx.ConnectError as e:
        logger.error(f"连接后端失败: {e}")
        yield f"data: {json.dumps({'type': 'response.error', 'error': {'type': 'connection_error', 'message': f'连接后端失败: {str(e)}'}}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return
    except httpx.TimeoutException as e:
        logger.error(f"请求超时: {e}")
        yield f"data: {json.dumps({'type': 'response.error', 'error': {'type': 'timeout_error', 'message': f'请求超时: {str(e)}'}}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return
    except Exception as e:
        logger.error(f"流式处理异常: {e}")
        yield f"data: {json.dumps({'type': 'response.error', 'error': {'type': 'internal_error', 'message': str(e)}}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # 发送 response.completed 事件
    completed_response = {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": payload.get("model", "mimo"),
        "output": [{
            "type": "message",
            "id": message_id,
            "role": "assistant",
            "status": "completed",
            "content": [],
        }],
    }

    if collected_reasoning:
        completed_response["output"][0]["content"].append({
            "type": "reasoning_text",
            "text": "".join(collected_reasoning),
        })
    if collected_content:
        completed_response["output"][0]["content"].append({
            "type": "output_text",
            "text": "".join(collected_content),
            "annotations": [],
        })

    yield f"data: {json.dumps({'type': 'response.completed', 'response': completed_response}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


async def verify_admin_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """验证配置管理 token"""
    if not config.admin_token:
        return True  # 未设置 token 时允许访问（本地开发）

    if not credentials or credentials.credentials != config.admin_token:
        raise HTTPException(status_code=401, detail="无效的认证 token")
    return True


@app.get("/config")
async def get_config(_: bool = Depends(verify_admin_token)):
    """获取当前配置"""
    codex_config = read_codex_config()
    api_type = detect_api_type(config.api_key) if config.api_key else "unknown"

    return {
        "proxy": {
            "host": config.host,
            "port": config.port,
            "backend_url": config.backend_url,
            "api_type": api_type,
            "enable_thinking": config.enable_thinking,
        },
        "codex": codex_config,
        "endpoints": MIMO_ENDPOINTS,
    }


@app.post("/config")
async def update_config(
    body: ConfigUpdate,
    _: bool = Depends(verify_admin_token),
):
    """更新配置（用于 cc-switch 集成）"""
    # 更新 API Key
    if body.api_key:
        config.api_key = body.api_key
        if not config.backend_url:
            config.backend_url = get_backend_url(config.api_key)

    # 更新后端 URL
    if body.backend_url:
        config.backend_url = body.backend_url

    # 更新思考模式
    if body.enable_thinking is not None:
        config.enable_thinking = body.enable_thinking

    # 写入 Codex 配置
    if body.write_codex and config.api_key:
        write_codex_config(
            api_key=config.api_key,
            base_url=f"http://{config.host}:{config.port}/v1",
            model=body.model,
        )

    logger.info("配置已更新")
    return {"status": "ok"}


@app.post("/v1/responses")
async def handle_responses(request: Request):
    """处理 Responses API 请求"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 JSON 请求体")

    # 验证请求体
    try:
        req = ResponsesRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求体验证失败: {str(e)}")

    # 支持通过请求头或请求体传递 API Key
    api_key = config.api_key
    backend_url = config.backend_url

    # 检查请求头中的 Authorization
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        request_key = auth_header[7:]
        if request_key:
            api_key = request_key
            backend_url = get_backend_url(api_key, "")

    # 检查请求体中的 api_key
    if req.api_key:
        api_key = req.api_key
        backend_url = get_backend_url(api_key, "")

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="缺少 API Key，请通过 Authorization 头或 api_key 参数提供",
        )

    # 转换为 Chat Completions 格式
    chat_payload = responses_to_chat_completions(body)

    # 构建后端请求
    url = f"{backend_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    logger.info(f"转发请求到 {url} (stream={req.stream})")

    async with httpx.AsyncClient(timeout=300.0) as client:
        if chat_payload.get("stream"):
            # 流式响应
            return StreamingResponse(
                stream_chat_completions(client, url, headers, chat_payload),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            # 非流式响应
            try:
                resp = await client.post(url, json=chat_payload, headers=headers)

                if resp.status_code != 200:
                    error_text = resp.text
                    logger.error(f"后端返回错误 {resp.status_code}: {error_text}")
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"后端错误: {error_text}",
                    )

                chat_result = resp.json()
                responses_result = chat_response_to_responses(chat_result)
                return JSONResponse(content=responses_result)

            except httpx.ConnectError as e:
                logger.error(f"连接后端失败: {e}")
                raise HTTPException(status_code=502, detail=f"连接后端失败: {str(e)}")
            except httpx.TimeoutException as e:
                logger.error(f"请求超时: {e}")
                raise HTTPException(status_code=504, detail=f"请求超时: {str(e)}")


@app.get("/v1/models")
async def list_models(request: Request):
    """模型列表（透传）"""
    api_key = config.api_key
    backend_url = config.backend_url

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        request_key = auth_header[7:]
        if request_key:
            api_key = request_key
            backend_url = get_backend_url(api_key, "")

    if not api_key:
        raise HTTPException(status_code=400, detail="缺少 API Key")

    url = f"{backend_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="获取模型列表失败")

            return JSONResponse(content=resp.json())
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"连接后端失败: {str(e)}")


@app.get("/health")
async def health():
    """健康检查"""
    api_type = detect_api_type(config.api_key) if config.api_key else "unknown"
    return {
        "status": "ok",
        "backend": config.backend_url or "auto-detect",
        "api_type": api_type,
    }


def main():
    parser = argparse.ArgumentParser(
        description="MIMO-to-Responses API 协议转换代理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 按量付费 (API Key: sk-xxxxx)
  python proxy.py --api-key sk-xxxxx

  # Token Plan (API Key: tp-xxxxx)
  python proxy.py --api-key tp-xxxxx

  # 自定义后端地址
  python proxy.py --api-key sk-xxxxx --backend https://api.xiaomimimo.com/v1

  # 禁用思考模式
  python proxy.py --api-key sk-xxxxx --no-thinking

  # 自动写入 Codex 配置（用于 cc-switch 集成）
  python proxy.py --api-key sk-xxxxx --write-codex

  # 启用配置管理认证
  python proxy.py --api-key sk-xxxxx --admin-token your-secret-token

cc-switch 集成:
  1. 启动代理: python proxy.py --api-key sk-xxxxx
  2. 在 cc-switch 中添加自定义 provider，base_url 设为: http://127.0.0.1:8888/v1
  3. 或使用 --write-codex 参数自动写入 Codex 配置
        """,
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="MIMO API Key（必需）。按量付费: sk-xxxxx，Token Plan: tp-xxxxx",
    )
    parser.add_argument(
        "--backend",
        default="",
        help="自定义后端地址（可选，默认根据 API Key 自动选择）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="代理监听端口 (默认: 8888)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="代理监听地址 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="禁用思考模式（reasoning_content）",
    )
    parser.add_argument(
        "--write-codex",
        action="store_true",
        help="自动写入 Codex 配置文件",
    )
    parser.add_argument(
        "--codex-dir",
        default="",
        help="自定义 Codex 配置目录（默认: ~/.codex）",
    )
    parser.add_argument(
        "--admin-token",
        default="",
        help="配置管理认证 token（可选，不设置则允许无认证访问）",
    )

    args = parser.parse_args()

    config.api_key = args.api_key
    config.backend_url = args.backend
    config.port = args.port
    config.host = args.host
    config.enable_thinking = not args.no_thinking
    config.codex_config_dir = args.codex_dir
    config.admin_token = args.admin_token

    # 自动检测后端地址
    if not config.backend_url:
        if config.api_key:
            config.backend_url = get_backend_url(config.api_key)
        else:
            config.backend_url = MIMO_ENDPOINTS["pay-as-you-go"]

    api_type = detect_api_type(config.api_key) if config.api_key else "unknown"

    print(f"MIMO-Responses 代理启动")
    print(f"   监听: {config.host}:{config.port}")
    print(f"   后端: {config.backend_url}")
    print(f"   计费模式: {api_type}")
    print(f"   思考模式: {'启用' if config.enable_thinking else '禁用'}")
    print(f"   认证: {'已启用' if config.admin_token else '未启用（本地开发模式）'}")
    print(f"   Responses API: http://{config.host}:{config.port}/v1/responses")
    print(f"   配置管理: http://{config.host}:{config.port}/config")

    if not config.api_key:
        print()
        print("警告: 未设置 API Key")
        print("   按量付费: 从 https://platform.xiaomimimo.com/#/console/api-keys 获取 (sk-xxxxx)")
        print("   Token Plan: 从 https://platform.xiaomimimo.com/#/console/plan-manage 获取 (tp-xxxxx)")

    # 自动写入 Codex 配置
    if args.write_codex and config.api_key:
        write_codex_config(
            api_key=config.api_key,
            base_url=f"http://{config.host}:{config.port}/v1",
        )
        print()
        print("已写入 Codex 配置:")
        print(f"   API Key: {config.api_key[:10]}...")
        print(f"   Base URL: http://{config.host}:{config.port}/v1")

    print()
    print("cc-switch 集成说明:")
    print("   1. 在 cc-switch 中添加自定义 provider")
    print(f"   2. Base URL 设为: http://{config.host}:{config.port}/v1")
    print("   3. API Key 设为你的 MIMO API Key")

    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
