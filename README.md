# OCR Server

通用验证码识别服务，基于 [ddddocr](https://github.com/sml2h3/ddddocr)。

## 部署

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 或一键部署
chmod +x deploy.sh && ./deploy.sh
```

## 启动

```bash
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 1224

# 或
.venv/bin/python main.py
```

## 接口

### GET /health

```json
{"success": true, "data": {"status": "ok"}}
```

### GET /info

```json
{
  "success": true,
  "data": {
    "engine": "ddddocr",
    "version": "1.6.1",
    "endpoints": {
      "base64": "POST /ocr/base64",
      "upload": "POST /ocr/upload"
    }
  }
}
```

### POST /ocr/base64

请求：

```json
{"image": "iVBORw0KGgoAAAANSUhEUgAA..."}
```

响应：

```json
{"success": true, "data": {"result": "8a3f", "length": 1186}}
```

### POST /ocr/upload

```bash
curl -X POST http://127.0.0.1:1224/ocr/upload -F "file=@captcha.png"
```

```json
{"success": true, "data": {"result": "8a3f", "length": 1186, "filename": "captcha.png"}}
```

## 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `OCR_HOST` | `127.0.0.1` | 监听地址 |
| `OCR_PORT` | `1224` | 监听端口 |

## 错误

| code | HTTP | 说明 |
|------|------|------|
| `INVALID_INPUT` | 400 | 图片为空或格式不支持 |
| `OCR_FAILED` | 500 | 识别失败 |
