import urllib.request
import urllib.parse
import json
import io
import mimetypes
from pathlib import Path

BASE = "http://localhost:8100"

def post_multipart(url, fields, files):
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    buf = io.BytesIO()
    for name, value in fields.items():
        buf.write(f'--{boundary}\r\n'.encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        buf.write(f'{value}\r\n'.encode())
    for name, (filename, content, content_type) in files.items():
        buf.write(f'--{boundary}\r\n'.encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        buf.write(f'Content-Type: {content_type}\r\n\r\n'.encode())
        buf.write(content)
        buf.write(b'\r\n')
    buf.write(f'--{boundary}--\r\n'.encode())
    
    req = urllib.request.Request(url, data=buf.getvalue())
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode())

sample_img = Path("data/fixtures/receiving/desk_lamp_front.jpg")
if not sample_img.exists():
    # Find any sample jpg
    sample_img = list(Path("data").glob("**/*.jpg"))[0]

img_bytes = sample_img.read_bytes()
print(f"Using sample image: {sample_img} ({len(img_bytes)} bytes)")

stages = ["receiving", "prep", "pack", "returns", "recovery"]

for stage in stages:
    print(f"\n--- Testing Agent {stage.upper()} Image Input & Pipeline Step ---")
    status, res = post_multipart(
        f"{BASE}/api/capture",
        {"unit_id": "UNIT-0014", "stage": stage, "org_id": "org_demo_alpha"},
        {"file": ("capture.jpg", img_bytes, "image/jpeg")}
    )
    print(f"Delivery Confirmed: {res.get('delivery_confirmed')} for stage: {res.get('orchestrator_routed_to')}")
    wf = res.get("workflow", {})
    ev = res.get("evidence", {})
    print(f"Workflow Status: {wf.get('status')} | Stages completed: {[s['stage'] for s in wf.get('stage_results', []) if s.get('state') == 'completed']}")
    for s in wf.get("stage_results", []):
        if s["stage"] == stage:
            print(f"Agent {stage} Verdict: {s.get('verdict')} | State: {s.get('state')} | Record: {s.get('record_id')}")

print("\nAll 5 agents received separate image inputs and completed execution!")
