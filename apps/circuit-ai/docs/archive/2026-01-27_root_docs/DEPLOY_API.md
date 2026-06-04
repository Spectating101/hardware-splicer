# Circuit-AI API deploy (no frontend)

## Local (Docker, API only)
- Start: `docker compose -f docker-compose.api.yml up --build`
- Health: `http://localhost:8000/healthz`
- Ready: `http://localhost:8000/readyz`

## Auth for testing
`docker-compose.api.yml` sets `TEST_API_KEYS=test` by default.

Example request:
- `curl -F file=@analyzed_pcb.png -H "Authorization: Bearer test" http://localhost:8000/analyze`

## Production env vars
- `JWT_SECRET` (strong random; required if `DEBUG=0`)
- `YOLO_MODEL_PATH` (defaults to `/app/yolov8n.pt`)
- `DETECTION_BACKEND` (`yolo`/`classical`/`remote`)
- `ENABLE_OCR` (`0` recommended unless you ship OCR deps/models)

