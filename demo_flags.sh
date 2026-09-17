#!/bin/bash
# Start latest server, demo the new "flags" feature on showcase sites, stop server.
cd "$(dirname "$0")"
.venv/Scripts/python -m uvicorn app:app --host 127.0.0.1 --port 9000 > /dev/null 2>&1 &
SRV=$!
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:9000/process?url=https://example.com" 2>/dev/null)
  if [ "$code" = "200" ]; then break; fi
  sleep 1
done
echo "=== IMPROVED ENDPOINT — new 'flags' field (UA rotation + JS-detect + thin-content) ==="
for u in "https://example.com" "https://httpbin.org/html" "https://www.techcrunch.com" "https://www.reddit.com/r/programming/"; do
  echo "--- $u ---"
  curl -s --max-time 15 "http://127.0.0.1:9000/process?url=$u" 2>&1 | head -c 400
  echo
done
kill $SRV 2>/dev/null
echo "=== demo done ==="
