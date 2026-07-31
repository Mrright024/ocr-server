"""
通用验证码识别服务

基于 ddddocr，提供 base64 和文件上传两种接口。
"""

import ast
from io import BytesIO
import logging
import math
import os
import unicodedata

import ddddocr
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
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
_arithmetic_ocr = None


class OcrBase64Request(BaseModel):
    image: str


def _evaluate_arithmetic(node: ast.AST):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value

    if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
        value = _evaluate_arithmetic(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value

    if isinstance(node, ast.BinOp):
        left = _evaluate_arithmetic(node.left)
        right = _evaluate_arithmetic(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right

    raise ValueError("不支持的算式")


def _normalize_arithmetic(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).translate(str.maketrans({
        "×": "*",
        "✕": "*",
        "✖": "*",
        "x": "*",
        "X": "*",
        "t": "+",
        "T": "+",
        "һ": "-",
        "÷": "/",
        "＋": "+",
        "－": "-",
        "−": "-",
        "加": "+",
        "减": "-",
        "乘": "*",
        "除": "/",
        "＝": "=",
    })).replace(" ", "")

    # Captchas commonly append an equals sign or question mark to the expression.
    normalized = normalized.rstrip("?")
    if normalized.endswith("="):
        normalized = normalized[:-1]
    return normalized


def _single_digit_expression_prefix(text: str) -> str:
    normalized = _normalize_arithmetic(text)
    if (
        len(normalized) >= 3
        and normalized[0].isdigit()
        and normalized[1] in "+-*/"
        and normalized[2].isdigit()
    ):
        return normalized[:3]
    return ""


def _solve_arithmetic(text: str) -> str:
    normalized = _normalize_arithmetic(text)

    if not normalized or len(normalized) > 64 or any(
        char not in "0123456789()+-*/." for char in normalized
    ):
        return text

    try:
        tree = ast.parse(normalized, mode="eval")
        value = _evaluate_arithmetic(tree.body)
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("算式结果无效")
            if value.is_integer():
                return str(int(value))
            return format(value, "g")
        return str(value)
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return text


def _get_arithmetic_ocr():
    global _arithmetic_ocr
    if _arithmetic_ocr is None:
        _arithmetic_ocr = ddddocr.DdddOcr(show_ad=False, beta=True)
    return _arithmetic_ocr


def _classify(image_bytes: bytes) -> str:
    result = _ocr.classification(image_bytes).strip()
    if not result:
        return result

    expression = _single_digit_expression_prefix(result)
    if expression:
        return expression
    if not result[0].isdigit():
        return result

    # Avoid extra OCR passes for ordinary alphanumeric captchas.
    has_ascii_operator = any(operator in result for operator in "+-*/xXtT")
    if result.isascii() and not has_ascii_operator:
        return result
    if not any(char.isdigit() for char in result):
        return result

    # ddddocr can read a trailing "=?" prompt as an extra digit. Try removing
    # a small right margin, but only accept an unambiguous simple expression.
    try:
        image = Image.open(BytesIO(image_bytes))
        max_trim = min(32, image.width - 2)
        for trim in range(4, max_trim + 1, 2):
            cropped = image.crop((0, 0, image.width - trim, image.height))
            buffer = BytesIO()
            cropped.save(buffer, format="PNG")
            candidate = _ocr.classification(buffer.getvalue()).strip()
            expression = _single_digit_expression_prefix(candidate)
            if expression:
                return expression

        # The beta model is slower and uses more memory, so only load it when
        # the default model could not recover a simple arithmetic expression.
        candidate = _get_arithmetic_ocr().classification(image_bytes).strip()
        expression = _single_digit_expression_prefix(candidate)
        if expression:
            return expression
    except Exception:
        logger.debug("算式验证码裁剪识别失败", exc_info=True)
    return result


def _recognize(image_bytes: bytes) -> str:
    if not image_bytes or len(image_bytes) == 0:
        raise ValueError("图片为空")
    result = _classify(image_bytes)
    if not result:
        raise ValueError("识别结果为空")
    return _solve_arithmetic(result)


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
