import json, os, re, subprocess, sys

# Read the stored credential
cred_path = os.path.expanduser("~/.git-credentials")
if not os.path.exists(cred_path):
    # try WINDOWS path
    cred_path = os.path.expandvars(r"%USERPROFILE%\.git-credentials")
raw = None
for p in [os.path.expanduser("~/.git-credentials"),
          os.path.join(os.environ.get("USERPROFILE",""),".git-credentials"),
          "/c/Users/Owner/.git-credentials"]:
    if os.path.exists(p):
        raw = open(p).read().strip()
        print("cred file:", p)
        break

if not raw:
    print("NO git-credentials file found")
    sys.exit(1)

# Format: https://USER:TOKEN@host  OR  https://TOKEN@host
m = re.match(r'^https://([^:]+):([^@]+)@github\.com', raw)
if m:
    user, token = m.group(1), m.group(2)
elif re.match(r'^https://([^@]+)@github\.com', raw):
    token = re.match(r'^https://([^@]+)@github\.com', raw).group(1)
    user = token
else:
    print("unparsed credential:", raw[:20], "...")
    sys.exit(1)

print("user:", user)
print("token len:", len(token), "prefix:", token[:4])

# 1. Create the GitHub repo via API
repo_name = "hermes-url-processor"
repo_url = f"https://api.github.com/user/repos"
payload = {"name": repo_name, "description": "AI web URL processor API built with Hermes Agent — GET /process?url=<url> returns structured page data. Free-tier, pay-per-call ready.", "public": True, "auto_init": True, "private": False}
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
import urllib.request
req = urllib.request.Request(repo_url, data=json.dumps(payload).encode(), headers=headers, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=20)
    data = json.load(resp)
    print("REPO CREATED:", data.get("html_url"))
    clone_url = data.get("clone_url")
except urllib.error.HTTPError as e:
    body = e.read().decode()[:300]
    print("HTTPError", e.code, body)
    if e.code == 422:
        clone_url = f"https://github.com/{user}/{repo_name}.git"
        print("repo may already exist, using:", clone_url)
    else:
        sys.exit(1)

# 2. Push the local repo to GitHub
subprocess.run("git config --global push.default simple", shell=True)
r = subprocess.run("git remote remove origin 2>/dev/null; git remote add origin " + clone_url, shell=True, cwd=os.path.expanduser("~/hermes-work/agent-demo"), capture_output=True, text=True)
print("remote add:", r.returncode)
r = subprocess.run("git -c credential.helper= push -u origin main 2>&1", shell=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "false"}, cwd=os.path.expanduser("~/hermes-work/agent-demo"), capture_output=True, text=True, timeout=60)
out = (r.stdout + r.stderr)[-800:]
print("PUSH:")
print(out)
