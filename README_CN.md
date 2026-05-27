<p align="center">
  <h1 align="center">MIMO Codex 桥接器</h1>
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>中文</strong>
</p>

<p align="center">
  轻量级协议转换代理，让 OpenAI Codex 能够使用小米 MIMO 模型。
</p>

---

## 功能特性

- **自动计费检测** - 根据 API Key 前缀（`sk-` / `tp-`）自动检测计费模式
- **思考模式** - 支持 MIMO 的 `reasoning_content` 链式思考
- **Tools 支持** - 完整转换 Responses API 和 Chat Completions 之间的函数调用
- **流式响应** - 实时 SSE 事件流式传输
- **cc-switch 集成** - 通过 [cc-switch](https://github.com/farion1231/cc-switch) 管理多个账号
- **便携打包** - 可打包为独立的 exe 文件

## 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行代理

**按量付费 (API Key: sk-xxxxx)**
```bash
python proxy.py --api-key sk-xxxxx
```

**Token Plan (API Key: tp-xxxxx)**
```bash
python proxy.py --api-key tp-xxxxx
```

**自动写入 Codex 配置**
```bash
python proxy.py --api-key sk-xxxxx --write-codex
```

**启用管理认证**
```bash
python proxy.py --api-key sk-xxxxx --admin-token your-secret-token
```

### 打包为 exe
```bash
build.bat
# 输出: dist/mimo-proxy.exe
```

## cc-switch 集成

[cc-switch](https://github.com/farion1231/cc-switch) 是一个管理多个 AI CLI 工具配置的桌面应用。

1. 启动代理：
   ```bash
   python proxy.py --api-key sk-xxxxx
   ```

2. 在 cc-switch 中添加自定义 provider：
   - **Base URL**: `http://127.0.0.1:8888/v1`
   - **API Key**: 你的 MIMO API Key

3. 或使用 `--write-codex` 自动写入 Codex 配置：
   ```bash
   python proxy.py --api-key sk-xxxxx --write-codex
   ```

## 参数说明

| 参数 | 说明 |
|------|------|
| `--api-key` | MIMO API Key（必需）。按量付费: `sk-xxxxx`，Token Plan: `tp-xxxxx` |
| `--backend` | 自定义后端地址（可选，默认根据 API Key 自动选择） |
| `--port` | 代理监听端口（默认: 8888） |
| `--host` | 代理监听地址（默认: 127.0.0.1） |
| `--no-thinking` | 禁用思考模式 |
| `--write-codex` | 自动写入 Codex 配置文件 |
| `--codex-dir` | 自定义 Codex 配置目录（默认: ~/.codex） |
| `--admin-token` | 管理认证 token（可选） |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/responses` | POST | Responses API 主端点 |
| `/v1/models` | GET | 模型列表（透传） |
| `/config` | GET | 获取当前配置 |
| `/config` | POST | 更新配置 |
| `/health` | GET | 健康检查 |

## 计费模式

| 模式 | API Key 格式 | 后端地址 |
|------|-------------|---------|
| 按量付费 | `sk-xxxxx` | `https://api.xiaomimimo.com/v1` |
| Token Plan | `tp-xxxxx` | `https://token-plan-cn.xiaomimimo.com/v1` |

## 获取 API Key

1. 访问 [MIMO 开放平台](https://platform.xiaomimimo.com)
2. 按量付费: 前往 [API Keys](https://platform.xiaomimimo.com/#/console/api-keys)
3. Token Plan: 前往 [订阅管理](https://platform.xiaomimimo.com/#/console/plan-manage)

## 安全说明

- `/config` 端点支持通过 `--admin-token` 参数启用 Bearer Token 认证
- 不设置 `--admin-token` 时，配置端点允许无认证访问（适用于本地开发）
- API Key 在日志中会被截断显示（仅显示前 10 个字符）

## 参考文档

- [MIMO 官方文档](https://platform.xiaomimimo.com/docs/zh-CN/welcome)
- [Claude Code 配置指南](https://platform.xiaomimimo.com/docs/zh-CN/integration/claudecode)
- [cc-switch GitHub](https://github.com/farion1231/cc-switch)
