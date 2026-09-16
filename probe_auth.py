import os, json
p = os.environ['LOCALAPPDATA'] + '\\opencode\\auth.json'
print('path:', p, 'exists:', os.path.exists(p))
if not os.path.exists(p):
    # try home .local share
    p2 = os.path.expanduser('~/.local/share/opencode/auth.json')
    print('try2:', p2, 'exists:', os.path.exists(p2))
    if os.path.exists(p2):
        p = p2
d = json.load(open(p))
def show(o, pre=''):
    if isinstance(o, dict):
        for k, v in o.items():
            if any(s in k.lower() for s in ['key', 'token', 'secret', 'pass']):
                print(pre + k, '=', '***SET len=%d***' % len(str(v)) if v else '(empty)')
            elif any(s in k.lower() for s in ['url', 'endpoint', 'base', 'host']):
                print(pre + k, '=', repr(v))
            else:
                show(v, pre + '  ' + k + ':')
    elif isinstance(o, list):
        print(pre, '[list of', len(o), ']')
show(d)
print('top keys:', list(d.keys()) if isinstance(d, dict) else type(d))
