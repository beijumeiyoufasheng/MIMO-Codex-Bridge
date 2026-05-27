#!/usr/bin/env python3
"""测试代理转换逻辑"""

import asyncio
import tempfile
import tomllib
from proxy import (
    responses_to_chat_completions,
    chat_response_to_responses,
    detect_api_type,
    get_backend_url,
    config,
    write_codex_config,
    _build_stream_completed_response,
    _stream_error,
    _redact_api_key,
    _replace_top_level_toml_value,
    _convert_tools,
    _merge_tool_call_deltas,
)


def test_responses_to_chat_completions():
    """测试 Responses API 到 Chat Completions 的转换"""
    print("=== 测试 Responses API -> Chat Completions 转换 ===\n")

    # 测试 1: 简单字符串输入
    test1 = {"input": "Hello", "model": "mimo-v2.5-pro"}
    result1 = responses_to_chat_completions(test1)
    assert result1["model"] == "mimo-v2.5-pro"
    assert result1["messages"] == [{"role": "user", "content": "Hello"}]
    print("[PASS] 测试 1 - 简单字符串输入")

    # 测试 2: 消息数组输入
    test2 = {
        "input": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ],
        "model": "mimo-v2.5-pro"
    }
    result2 = responses_to_chat_completions(test2)
    assert len(result2["messages"]) == 2
    assert result2["messages"][0]["role"] == "system"
    print("[PASS] 测试 2 - 消息数组输入")

    # 测试 3: 带 instructions
    test3 = {
        "input": "Hello",
        "instructions": "You are a helpful assistant.",
        "model": "mimo-v2.5-pro"
    }
    result3 = responses_to_chat_completions(test3)
    assert result3["messages"][0]["role"] == "system"
    assert result3["messages"][0]["content"] == "You are a helpful assistant."
    print("[PASS] 测试 3 - 带 instructions")

    # 测试 4: 带 tools 参数
    test4 = {
        "input": "What's the weather?",
        "tools": [
            {
                "type": "function",
                "name": "get_weather",
                "description": "Get weather info",
                "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}
            }
        ],
        "tool_choice": {"type": "function", "name": "get_weather"},
    }
    result4 = responses_to_chat_completions(test4)
    assert "tools" in result4
    assert len(result4["tools"]) == 1
    assert result4["tools"][0]["function"]["name"] == "get_weather"
    assert result4["tool_choice"]["function"]["name"] == "get_weather"
    print("[PASS] 测试 4 - 带 tools 参数")

    # 测试 5: reasoning_content 保留
    test5 = {
        "input": [
            {
                "role": "assistant",
                "content": "Let me think...",
                "reasoning_content": "Thinking process here"
            },
            {"role": "user", "content": "Continue"}
        ]
    }
    result5 = responses_to_chat_completions(test5)
    assert result5["messages"][0].get("reasoning_content") == "Thinking process here"
    print("[PASS] 测试 5 - reasoning_content 保留")

    # 测试 6: 工具结果回传
    test6 = {
        "input": [
            {"type": "function_call", "call_id": "call_123", "name": "get_weather", "arguments": '{"location":"Beijing"}'},
            {"type": "function_call_output", "call_id": "call_123", "output": "Sunny 25C"},
        ]
    }
    result6 = responses_to_chat_completions(test6)
    assert result6["messages"][0]["role"] == "assistant"
    assert result6["messages"][0]["tool_calls"][0]["id"] == "call_123"
    assert result6["messages"][1]["role"] == "tool"
    assert result6["messages"][1]["tool_call_id"] == "call_123"
    print("[PASS] 测试 6 - 工具结果回传")


def test_chat_response_to_responses():
    """测试 Chat Completions 到 Responses API 的转换"""
    print("\n=== 测试 Chat Completions -> Responses API 转换 ===\n")

    # 测试 1: 普通响应
    test1 = {
        "model": "mimo-v2.5-pro",
        "choices": [{
            "message": {
                "content": "Hello! How can I help you?",
                "role": "assistant"
            }
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    }
    result1 = chat_response_to_responses(test1)
    assert result1["status"] == "completed"
    assert result1["output"][0]["content"][0]["type"] == "output_text"
    assert result1["output"][0]["content"][0]["text"] == "Hello! How can I help you?"
    print("[PASS] 测试 1 - 普通响应")

    # 测试 2: 带 reasoning_content 的响应
    test2 = {
        "model": "mimo-v2.5-pro",
        "choices": [{
            "message": {
                "content": "The answer is 42.",
                "reasoning_content": "Let me think about this...",
                "role": "assistant"
            }
        }]
    }
    result2 = chat_response_to_responses(test2)
    assert len(result2["output"][0]["content"]) == 2
    assert result2["output"][0]["content"][0]["type"] == "reasoning_text"
    assert result2["output"][0]["content"][1]["type"] == "output_text"
    print("[PASS] 测试 2 - 带 reasoning_content")

    # 测试 3: 带 tool_calls 的响应
    test3 = {
        "model": "mimo-v2.5-pro",
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [{
                    "id": "call_123",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "Beijing"}'
                    }
                }]
            }
        }]
    }
    result3 = chat_response_to_responses(test3)
    assert result3["output"][0]["type"] == "function_call"
    assert result3["output"][0]["call_id"] == "call_123"
    assert result3["output"][0]["name"] == "get_weather"
    print("[PASS] 测试 3 - 带 tool_calls")


def test_convert_tools():
    """测试 tools 转换"""
    print("\n=== 测试 Tools 转换 ===\n")

    # 测试 Responses API 格式转换
    tools = [
        {
            "type": "function",
            "name": "get_weather",
            "description": "Get weather info",
            "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}
        }
    ]
    result = _convert_tools(tools)
    assert result[0]["type"] == "function"
    assert result[0]["function"]["name"] == "get_weather"
    print("[PASS] 测试 Responses API 格式转换")

    # 测试已有的 Chat Completions 格式
    tools_cc = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather info",
                "parameters": {}
            }
        }
    ]
    result_cc = _convert_tools(tools_cc)
    assert result_cc[0]["function"]["name"] == "get_weather"
    print("[PASS] 测试 Chat Completions 格式透传")

    # 测试过滤不支持的内置工具
    unsupported_tools = [{"type": "web_search", "external_web_access": False}]
    result_unsupported = _convert_tools(unsupported_tools)
    assert result_unsupported == []
    print("[PASS] 测试过滤不支持的内置工具")

    # 测试过滤缺少 function.name 的工具
    invalid_tools = [{"type": "function", "function": {"description": "missing name"}}]
    result_invalid = _convert_tools(invalid_tools)
    assert result_invalid == []
    print("[PASS] 测试过滤缺少名称的工具")


def test_merge_tool_call_deltas():
    """测试流式 tool_call delta 聚合"""
    print("\n=== 测试流式 Tool Call 聚合 ===\n")

    collected = []
    _merge_tool_call_deltas(collected, [{"index": 0, "id": "call_123", "type": "function", "function": {"name": "get_"}}])
    _merge_tool_call_deltas(collected, [{"index": 0, "function": {"name": "weather", "arguments": '{"location"'}}])
    _merge_tool_call_deltas(collected, [{"index": 0, "function": {"arguments": ':"Beijing"}'}}])

    assert collected[0]["id"] == "call_123"
    assert collected[0]["function"]["name"] == "get_weather"
    assert collected[0]["function"]["arguments"] == '{"location":"Beijing"}'
    print("[PASS] 测试流式 tool_call delta 聚合")


def test_api_key_detection():
    """测试 API Key 类型检测"""
    print("\n=== 测试 API Key 类型检测 ===\n")

    test_cases = [
        ("sk-abc123", "pay-as-you-go"),
        ("tp-xyz789", "token-plan"),
        ("other-key", "pay-as-you-go"),
    ]

    for key, expected in test_cases:
        api_type = detect_api_type(key)
        url = get_backend_url(key)
        assert api_type == expected, f"Expected {expected}, got {api_type}"
        print(f"[PASS] {key} -> {api_type} ({url})")


def test_codex_config_merge_matches_exact_toml_keys():
    """测试 Codex TOML 合并只替换顶层精确键"""
    print("\n=== 测试 Codex 配置合并 ===\n")

    lines = [
        'model_provider = "keep"\n',
        'base_url = "old"\n',
        '[profiles.default]\n',
        'model = "nested-keep"\n',
    ]
    result, replaced = _replace_top_level_toml_value(lines, "model", "new-model")

    assert replaced is False
    assert result == lines
    print("[PASS] 测试不误改相似键和表内键")


def test_write_codex_config_preserves_unrelated_toml_keys():
    """测试写 Codex 配置保留无关 TOML 键"""
    print("\n=== 测试 Codex 配置写入 ===\n")

    old_codex_dir = config.codex_config_dir
    try:
        with tempfile.TemporaryDirectory(dir=r"C:\tmp") as temp_dir:
            config.codex_config_dir = temp_dir
            config_file = config.get_codex_config_dir() / "config.toml"
            config_file.write_text(
                'model_provider = "keep"\n'
                '[profiles.default]\n'
                'model = "nested-keep"\n',
                encoding="utf-8",
            )

            write_codex_config("sk-secret", 'http://127.0.0.1:8888/v1', 'mimo "quoted"')

            written = config_file.read_text(encoding="utf-8")
            assert 'model_provider = "keep"' in written
            assert 'model = "nested-keep"' in written
            assert 'base_url = "http://127.0.0.1:8888/v1"' in written
            assert 'model = "mimo \\"quoted\\""' in written
            parsed = tomllib.loads(written)
            assert parsed["base_url"] == "http://127.0.0.1:8888/v1"
            assert parsed["model"] == 'mimo "quoted"'
            assert parsed["model_provider"] == "keep"
            assert parsed["profiles"]["default"]["model"] == "nested-keep"
    finally:
        config.codex_config_dir = old_codex_dir
    print("[PASS] 测试备份合并写入")


def test_stream_error_emits_failed_response_for_backend_errors():
    """测试流式错误统一包含 response.failed"""
    print("\n=== 测试流式错误事件 ===\n")

    async def collect_events():
        return [
            event
            async for event in _stream_error(
                "backend_error",
                "backend failed",
                "resp_test",
                {"model": "mimo-v2.5-pro"},
                code=500,
            )
        ]

    events = asyncio.run(collect_events())
    assert any('"type": "response.failed"' in event for event in events)
    assert any('"code": 500' in event for event in events)
    print("[PASS] 测试流式错误 response.failed")


def test_completed_stream_message_contains_final_content():
    """测试流式完成响应和 item done 带最终内容"""
    print("\n=== 测试流式完成内容 ===\n")

    completed = _build_stream_completed_response(
        response_id="resp_test",
        message_id="msg_test",
        payload={"model": "mimo-v2.5-pro"},
        collected_reasoning=["think"],
        collected_content=["answer"],
        collected_tool_calls=[],
    )

    content = completed["output"][0]["content"]
    assert content[0]["type"] == "reasoning_text"
    assert content[1]["text"] == "answer"
    print("[PASS] 测试完成消息内容")


def test_api_key_redaction_uses_short_prefix():
    """测试 API Key 只展示短前缀"""
    print("\n=== 测试 API Key 脱敏 ===\n")

    assert _redact_api_key("sk-1234567890") == "sk-1..."
    print("[PASS] 测试 API Key 短脱敏")


if __name__ == "__main__":
    test_responses_to_chat_completions()
    test_chat_response_to_responses()
    test_convert_tools()
    test_merge_tool_call_deltas()
    test_api_key_detection()
    test_codex_config_merge_matches_exact_toml_keys()
    test_write_codex_config_preserves_unrelated_toml_keys()
    test_stream_error_emits_failed_response_for_backend_errors()
    test_completed_stream_message_contains_final_content()
    test_api_key_redaction_uses_short_prefix()
    print("\n[OK] 所有测试完成")
