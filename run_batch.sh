#!/bin/bash
# Start server → run 50-URL batch → stop server (all in one process)
cd "$(dirname "$0")"

# 1. Start the API server in the background
.venv/Scripts/python -m uvicorn app:app --host 127.0.0.1 --port 9000 > /dev/null 2>&1 &
SRV=$!

# 2. Wait for readiness
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:9000/process?url=https://example.com" 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "server ready after ${i}s"
    break
  fi
  sleep 1
done

# 3. Run the 50-URL audit batch against localhost
urls=(
"https://bbc.com/news" "https://example.com" "https://httpbin.org/html"
"https://en.wikipedia.org/wiki/Artificial_intelligence" "https://www.apple.com"
"https://www.microsoft.com/en-us/microsoft-365/blog" "https://www.nytimes.com" "https://www.bbc.com/sport"
"https://en.wikipedia.org/wiki/Machine_learning" "https://www.python.org" "https://www.python.org/about/"
"https://docs.python.org/3/library/urllib.html" "https://www.w3.org/TR/html401/" "https://developer.mozilla.org/en-US/docs/Web/HTML/Element/Heading"
"https://en.wikipedia.org/wiki/Data_scraping" "https://www.reddit.com/r/programming/" "https://www.reddit.com/r/MachineLearning/"
"https://www.imdb.com/title/tt0111161/" "https://www.gutenberg.org/ebooks/1342" "https://www.ycombinator.com/blog/"
"https://techcrunch.com" "https://www.theverge.com" "https://www.engadget.com" "https://arstechnica.com"
"https://www.cnn.com" "https://www.forbes.com" "https://www.bloomberg.com" "https://www.reuters.com"
"https://www.shopify.com/blog" "https://www.shopify.com/enterprise" "https://www.smashingmagazine.com"
"https://css-tricks.com" "https://www.a16z.com" "https://www.ycombinator.com/library/"
"https://en.wikipedia.org/wiki/Digital_marketing" "https://moz.com/blog" "https://ahrefs.com/blog"
"https://neilpatel.com/blog" "https://backlinko.com/blog" "https://coppyblogger.com"
"https://copyhackers.com" "https://blog.hubspot.com" "https://buffer.com/resources"
)

printf "url,domain,title,total_words,h1_count,status,issue\n" > audit50.csv
n=0
for u in "${urls[@]}"; do
  n=$((n+1))
  res=$(timeout 12 curl -s "http://127.0.0.1:9000/process?url=$u" 2>&1)
  if echo "$res" | grep -q '"h1_count"'; then
    domain=$(echo "$res" | sed -n 's/.*"domain":"\([^"]*\)".*/\1/p')
    title=$(echo "$res" | sed -n 's/.*"title":"\([^"]*\)".*/\1/p' | head -1)
    words=$(echo "$res" | sed -n 's/.*"total_words":\([0-9]*\).*/\1/p')
    h1=$(echo "$res" | sed -n 's/.*"h1_count":\([0-9]*\).*/\1/p')
    code=$(echo "$res" | sed -n 's/.*"status":\([0-9]*\).*/\1/p' | head -1)
    issue="ok"
    if [ -n "$words" ] && [ "$words" -lt 300 ] 2>/dev/null; then issue="thin content (<300 words)"; fi
    if [ -z "$title" ]; then issue="missing title"; fi
    if [ "$h1" = "0" ]; then issue="no H1 tag"; fi
    printf '"%s","%s","%s",%s,%s,%s,"%s"\n' "$u" "$domain" "$title" "$words" "$h1" "$code" "$issue" >> audit50.csv
    st="$code"
  else
    err=$(echo "$res" | grep -oE '"error":"[^"]*"' | head -1 | sed 's/"error":"//;s/"$//')
    printf '"%s",ERROR,,,,,"blocked/error"\n' "$u" >> audit50.csv
    st="ERR"
  fi
  echo "[$n/50] $st $u"
done

# 4. Stop the server
kill $SRV 2>/dev/null
echo "=== BATCH DONE ==="
wc -l audit50.csv
