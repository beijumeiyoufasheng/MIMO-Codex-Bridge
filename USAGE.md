# MIMO Codex Bridge - Usage Guide

## Quick Start

### Method 1: Interactive Start (Recommended for beginners)

Double-click `start.bat`, follow the prompts to enter your API Key and select options.

### Method 2: Command Line

```bash
# Pay-as-you-go
python proxy.py --api-key sk-xxxxx

# Token Plan
python proxy.py --api-key tp-xxxxx

# With all options
python proxy.py --api-key sk-xxxxx --port 8888 --host 127.0.0.1 --admin-token mysecret
```

### Method 3: Using the packaged exe

```bash
# Basic usage
mimo-proxy.exe --api-key sk-xxxxx

# With options
mimo-proxy.exe --api-key sk-xxxxx --write-codex --admin-token mysecret
```

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `--api-key` | Your MIMO API Key (required) | - |
| `--backend` | Custom backend URL | Auto-detect by API Key |
| `--port` | Proxy listening port | 8888 |
| `--host` | Proxy listening address | 127.0.0.1 |
| `--no-thinking` | Disable thinking mode | Enabled |
| `--write-codex` | Auto-write Codex config | Disabled |
| `--codex-dir` | Custom Codex config dir | ~/.codex |
| `--admin-token` | Admin auth token | No auth |

## After Starting the Proxy

1. The proxy will display:
   ```
   MIMO-Responses 代理启动
      监听: 127.0.0.1:8888
      后端: https://api.xiaomimimo.com/v1
      Responses API: http://127.0.0.1:8888/v1/responses
   ```

2. Configure Codex or cc-switch to use `http://127.0.0.1:8888/v1` as the base URL.

## cc-switch Integration

1. Start the proxy first
2. Open cc-switch
3. Add a new provider with:
   - **Base URL**: `http://127.0.0.1:8888/v1`
   - **API Key**: Your MIMO API Key
4. Enable the provider

## Troubleshooting

### "python is not recognized"
Install Python from https://python.org and add to PATH.

### "No module named fastapi"
Run: `pip install -r requirements.txt`

### Connection refused
Make sure the proxy is running and check the port number.

### API Key invalid
Verify your API Key at https://platform.xiaomimimo.com
