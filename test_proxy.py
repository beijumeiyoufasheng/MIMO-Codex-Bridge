#!/usr/bin/env python3
"""测试代理转换逻辑"""

import json
from proxy import (
    responses_to_chat_completions,
    chat_response_to_responses,
    detect_api_type,
    get_backend_url,
    MIMO_ENDPOINTS,
    _convert_tools,
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
        ]
    }
    result4 = responses_to_chat_completions(test4)
    assert "tools" in result4
    assert len(result4["tools"]) == 1
    assert result4["tools"][0]["function"]["name"] == "get_weather"
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
    assert result3["output"][0]["content"][0]["type"] == "tool_call"
    assert result3["output"][0]["content"][0]["id"] == "call_123"
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


if __name__ == "__main__":
    test_responses_to_chat_completions()
    test_chat_response_to_responses()
    test_convert_tools()
    test_api_key_detection()
    print("\n[OK] 所有测试完成")
