from __future__ import annotations
import base64, json, mimetypes, os
from pathlib import Path
from typing import Any
from .prompts import SYSTEM_PROMPT, user_prompt

class VisionError(RuntimeError): pass

def _data_url(path: Path) -> str:
    mime=mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"

def _resolve_ref(ref: str, input_root: Path) -> Path | None:
    p=Path(ref)
    candidates=[p] if p.is_absolute() else [input_root/p, Path.cwd()/p, Path(__file__).resolve().parents[3]/p]
    return next((c for c in candidates if c.is_file()),None)

def observe(images: list[dict[str,Any]], expected: list[dict[str,Any]], *, model: str, input_root: Path):
    if not images: raise VisionError("no_pack_capture")
    paths=[p for x in images if (p:=_resolve_ref(str(x["ref"]),input_root)) and p.suffix.lower() in {".jpg",".jpeg",".png",".webp"}]
    if not paths: raise VisionError("pack_image_not_found")
    try: from openai import OpenAI
    except Exception as exc: raise VisionError(f"openai_client_unavailable: {exc}") from exc
    if not os.getenv("OPENAI_API_KEY"): raise VisionError("OPENAI_API_KEY_missing")
    content=[{"type":"text","text":user_prompt(json.dumps(expected,ensure_ascii=False,indent=2))}]
    for p in paths: content.append({"type":"image_url","image_url":{"url":_data_url(p),"detail":"high"}})
    client=OpenAI()
    resp=client.chat.completions.create(model=model,messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":content}],response_format={"type":"json_object"},temperature=0)
    raw=resp.choices[0].message.content or "{}"
    try: parsed=json.loads(raw)
    except json.JSONDecodeError as exc: raise VisionError("model_returned_invalid_json") from exc
    if not isinstance(parsed.get("items"),list): raise VisionError("model_response_missing_items")
    return parsed["items"],{"name":model,"version":model,"provider":"openai","prompt_version":"pack-vision-v1","calls":1,"cost_usd":None,"uncertain":bool(parsed.get("uncertain")),"uncertain_reasons":parsed.get("uncertain_reasons") or []}
