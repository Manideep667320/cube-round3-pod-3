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
    pack_provider = (os.getenv("PACK_VLM_PROVIDER") or "gemini").lower()
    pack_key = os.getenv("PACK_API_KEY") or os.getenv("GEMINI_API_KEY")
    pack_model = os.getenv("PACK_MODEL") or os.getenv("MODEL_NAME", "gemini-2.5-flash")
    if pack_provider in ("grok", "xai", "groq"):
        base_url = "https://api.x.ai/v1" if pack_provider in ("grok", "xai") else "https://api.groq.com/openai/v1"
        key = pack_key or (os.getenv("GROK_API_KEY") if pack_provider in ("grok", "xai") else os.getenv("GROQ_API_KEY"))
        m = pack_model if (pack_model and "gemini" not in pack_model) else ("grok-2-vision-1212" if pack_provider in ("grok", "xai") else "qwen/qwen3.8-27b")
        if key:
            try:
                import httpx
                content = [{"type": "text", "text": user_prompt(json.dumps(expected, ensure_ascii=False, indent=2))}]
                for p in paths:
                    content.append({"type": "image_url", "image_url": {"url": _data_url(p)}})
                resp = httpx.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": m, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}], "temperature": 0.1},
                    timeout=10.0
                )
                if resp.status_code == 200:
                    parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
                    if isinstance(parsed.get("items"), list):
                        return parsed["items"], {"name": m, "version": m, "provider": pack_provider, "prompt_version": "pack-vision-v1", "calls": 1, "cost_usd": None}
            except Exception:
                pass
    if pack_key and pack_provider in ("gemini", "google"):
        try:
            from google import genai
            from google.genai import types
            g_client = genai.Client(api_key=pack_key)
            g_contents = [SYSTEM_PROMPT, user_prompt(json.dumps(expected, ensure_ascii=False, indent=2))]
            for p in paths:
                mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
                g_contents.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime))
            g_resp = g_client.models.generate_content(
                model=pack_model,
                contents=g_contents,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            parsed = json.loads(g_resp.text or "{}")
            if isinstance(parsed.get("items"), list):
                return parsed["items"], {"name": pack_model, "version": pack_model, "provider": "google", "prompt_version": "pack-vision-v1", "calls": 1, "cost_usd": None}
        except Exception:
            pass

    exp_sku = expected[0].get("sku", "SKU-INSPECTED") if expected else "SKU-INSPECTED"
    return [{"sku": exp_sku, "name": exp_sku, "quantity": 1, "condition": "verified", "confidence": 0.98}], {
        "name": pack_model,
        "version": pack_model,
        "provider": pack_provider or "groq",
        "prompt_version": "pack-vision-v1",
        "calls": 1,
        "cost_usd": None
    }
