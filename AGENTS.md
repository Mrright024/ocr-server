# Agent Notes

## Project Shape

- This is a single-service FastAPI application. `main.py` exports the ASGI app as `app` and owns all routes and OCR logic; there are no package boundaries or generated sources.
- The ddddocr model is created at module import (`_ocr = ddddocr.DdddOcr(...)`), so importing or starting the app requires the installed OCR dependencies and may load the model immediately.
- Arithmetic CAPTCHA handling is in `main.py`: safe AST evaluation computes recognized expressions, while right-edge crop retries and a lazy beta-model fallback handle upstream `=?` prompts that ddddocr may read as digits.

## Setup And Run

- The documented environment is a Python virtualenv: `python3 -m venv .venv` followed by `.venv/bin/pip install -r requirements.txt`.
- Run the app with `.venv/bin/uvicorn main:app --host 127.0.0.1 --port 1224`, or with `.venv/bin/python main.py`.
- `python main.py` accepts `--host` and `--port`; `OCR_HOST` and `OCR_PORT` provide its defaults. The systemd unit invokes uvicorn directly and hardcodes `127.0.0.1:1224`, so those environment variables do not change service deployment.

## Verification

- There is no repository test, lint, typecheck, or formatter configuration. At minimum, run `python -m compileall main.py` after Python changes.
- For endpoint changes, start the server and check `GET /health` and `GET /info`; OCR request behavior can be checked with the base64 or multipart examples in `README.md`.

## Deployment

- `deploy.sh` is a Linux/bash script that installs dependencies, renders `ocr-server.service`, and uses `sudo systemctl`; it is not a local Windows deployment path. It accepts an optional deployment directory argument and expects `main.py`, `requirements.txt`, and `ocr-server.service` there.
- The service listens only on loopback and uses port `1224` unless `ocr-server.service` is edited; use the script's final `systemctl`/`journalctl` commands to inspect the deployed service.
