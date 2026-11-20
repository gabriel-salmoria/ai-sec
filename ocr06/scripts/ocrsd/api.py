# Minimal OCRSD API client. Reads the workspace key from ~/.config/ocrsd/workspace and sends
# it only to ocrsd.onrcpn.org.br; never prints it.
import json, os, sys, urllib.request

BASE = "https://ocrsd.onrcpn.org.br"
# OCRSD_WORKSPACE_FILE picks another workspace (a second fetcher runs on its own quota).
TOKEN = open(os.path.expanduser(os.environ.get("OCRSD_WORKSPACE_FILE", "~/.config/ocrsd/workspace"))).read().strip()


def call(method, path, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"x-workspace-token": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = r.read()
    return payload if raw else json.loads(payload or b"null")


if __name__ == "__main__":
    method, path = sys.argv[1], sys.argv[2]
    body = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    print(json.dumps(call(method, path, body), ensure_ascii=False, indent=1)[:int(os.environ.get("MAXC", "4000"))])
