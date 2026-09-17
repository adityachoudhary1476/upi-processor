#!/bin/bash
# Keep the API server + public tunnel alive together in one process.
cd "$(dirname "$0")"
.venv/Scripts/python -m uvicorn app:app --host 0.0.0.0 --port 9000 &
SRV=$!
# wait for server readiness
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:9000/process?url=https://example.com" 2>/dev/null)
  [ "$code" = "200" ] && break
  sleep 1
done
echo "server up on 9000, attaching public tunnel..." >&2
# tunnel blocks — keeps process + server alive
npx --yes localtunnel --port 9000 --subdomain hermes-url-api
# if tunnel exits, clean up server
kill $SRV 2>/dev/null
