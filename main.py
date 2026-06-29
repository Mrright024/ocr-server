"""
通用验证码识别服务

基于 ddddocr，提供 base64 和文件上传两种接口。
"""

import logging
import os

import ddddocr
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import base64

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ocr")

app = FastAPI(title="OCR Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 模型在启动时加载（全局单例）
_ocr = ddddocr.DdddOcr(show_ad=False)


class OcrBase64Request(BaseModel):
    image: str


def _recognize(image_bytes: bytes) -> str:
    if not image_bytes or len(image_bytes) == 0:
        raise ValueError("图片为空")
    result = _ocr.classification(image_bytes).strip()
    if not result:
        raise ValueError("识别结果为空")
    return result


def _ok(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse({"success": True, "data": data}, status_code=status)


def _err(code: str, message: str, status: int = 500) -> JSONResponse:
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status,
    )


@app.get("/")
@app.get("/health")
async def health():
    return _ok({"status": "ok"})


@app.get("/info")
async def info():
    return _ok({
        "engine": "ddddocr",
        "version": getattr(ddddocr, "__version__", "unknown"),
        "endpoints": {
            "base64": "POST /ocr/base64",
            "upload": "POST /ocr/upload",
        },
    })


@app.post("/ocr/base64")
async def ocr_base64(req: OcrBase64Request):
    try:
        image_bytes = base64.b64decode(req.image)
        result = _recognize(image_bytes)
        logger.info("base64 识别: %d bytes → %s", len(image_bytes), result)
        return _ok({"result": result, "length": len(image_bytes)})
    except ValueError as e:
        return _err("INVALID_INPUT", str(e), 400)
    except Exception as e:
        logger.error("识别失败: %s", e)
        return _err("OCR_FAILED", str(e), 500)


@app.post("/ocr/upload")
async def ocr_upload(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        result = _recognize(image_bytes)
        logger.info("upload 识别: %s (%d bytes) → %s", file.filename, len(image_bytes), result)
        return _ok({
            "result": result,
            "length": len(image_bytes),
            "filename": file.filename,
        })
    except ValueError as e:
        return _err("INVALID_INPUT", str(e), 400)
    except Exception as e:
        logger.error("识别失败: %s", e)
        return _err("OCR_FAILED", str(e), 500)


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="OCR Server")
    parser.add_argument("--host", default=os.environ.get("OCR_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OCR_PORT", "1224")))
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
