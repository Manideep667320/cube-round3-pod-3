import urllib.request
import json
import mimetypes
from pathlib import Path

BASE = "http://localhost:8100"

def get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read()

# 1. Test health
status, body = get("/health")
print("Health:", status, json.loads(body.decode()))

# 2. Test lan-ip with stages
for stage in ["receiving", "prep", "pack", "returns", "recovery"]:
    status, body = get(f"/api/lan-ip?stage={stage}")
    data = json.loads(body.decode())
    print(f"Lan IP ({stage}):", data["scanner_url"])

# 3. Test scanner-qr with stages
for stage in ["receiving", "prep", "pack", "returns", "recovery"]:
    status, body = get(f"/api/scanner-qr?stage={stage}")
    print(f"QR ({stage}):", status, f"len={len(body)} bytes")

print("All endpoints tested successfully.")
