<p align="center">
  <h1 align="center">MIMO Codex Bridge</h1>
</p>

<p align="center">
  <strong>English</strong> | <a href="README_CN.md">中文</a>
</p>

<p align="center">
  A lightweight protocol conversion proxy that enables OpenAI Codex to use Xiaomi's MIMO models.
</p>

---

## Features

- **Auto Billing Detection** - Automatically detects billing mode based on API Key prefix (`sk-` / `tp-`)
- **Thinking Mode** - Supports MIMO's `reasoning_content` for chain-of-thought reasoning
- **Tools Support** - Full conversion of function calling between Responses API and Chat Completions
- **Streaming** - Real-time streaming response with SSE events
- **cc-switch Integration** - Manage multiple accounts via [cc-switch](https://github.com/farion1231/cc-switch)
- **Portable** - Can be packaged as a standalone .exe file

## Quick Start

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run the Proxy

**Pay-as-you-go (API Key: sk-xxxxx)**
```bash
python proxy.py --api-key sk-xxxxx
```

**Token Plan (API Key: tp-xxxxx)**
```bash
python proxy.py --api-key tp-xxxxx
```

**Auto-write Codex Config**
```bash
python proxy.py --api-key sk-xxxxx --write-codex
```

**Enable Admin Authentication**
```bash
python proxy.py --api-key sk-xxxxx --admin-token your-secret-token
```

### Package as exe
```bash
build.bat
# Output: dist/mimo-proxy.exe
```

## cc-switch Integration

[cc-switch](https://github.com/farion1231/cc-switch) is a desktop app for managing multiple AI CLI tool configurations.

1. Start the proxy:
   ```bash
   python proxy.py --api-key sk-xxxxx
   ```

2. In cc-switch, add a custom provider:
   - **Base URL**: `http://127.0.0.1:8888/v1`
   - **API Key**: Your MIMO API Key

3. Or use `--write-codex` to auto-write Codex config:
   ```bash
   python proxy.py --api-key sk-xxxxx --write-codex
   ```

## Parameters

| Parameter | Description |
|-----------|-------------|
| `--api-key` | MIMO API Key (required). Pay-as-you-go: `sk-xxxxx`, Token Plan: `tp-xxxxx` |
| `--backend` | Custom backend URL (optional, auto-detected by API Key) |
| `--port` | Proxy listening port (default: 8888) |
| `--host` | Proxy listening address (default: 127.0.0.1) |
| `--no-thinking` | Disable thinking mode |
| `--write-codex` | Auto-write Codex config file |
| `--codex-dir` | Custom Codex config directory (default: ~/.codex) |
| `--admin-token` | Admin authentication token (optional) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/responses` | POST | Responses API main endpoint |
| `/v1/models` | GET | Model list (passthrough) |
| `/config` | GET | Get current config |
| `/config` | POST | Update config |
| `/health` | GET | Health check |

## Billing Modes

| Mode | API Key Format | Backend URL |
|------|---------------|-------------|
| Pay-as-you-go | `sk-xxxxx` | `https://api.xiaomimimo.com/v1` |
| Token Plan | `tp-xxxxx` | `https://token-plan-cn.xiaomimimo.com/v1` |

## Get API Key

1. Visit [MIMO Platform](https://platform.xiaomimimo.com)
2. Pay-as-you-go: Go to [API Keys](https://platform.xiaomimimo.com/#/console/api-keys)
3. Token Plan: Go to [Subscription Management](https://platform.xiaomimimo.com/#/console/plan-manage)

## Security

- `/config` endpoint supports Bearer Token authentication via `--admin-token`
- Without `--admin-token`, config endpoint allows unauthenticated access (for local development)
- API Keys are truncated in logs (only first 10 characters shown)

## References

- [MIMO Documentation](https://platform.xiaomimimo.com/docs/zh-CN/welcome)
- [Claude Code Guide](https://platform.xiaomimimo.com/docs/zh-CN/integration/claudecode)
- [cc-switch GitHub](https://github.com/farion1231/cc-switch)
