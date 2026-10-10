import re
from pathlib import Path

ROOT = Path(r"c:\Users\manid\Documents\cube-round3-pod-3\orchestration\static")
EMOJI_PATTERN = re.compile(r'[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\ufe00-\ufe0f\u200d\u25b2\u25bc\u2605\u2606\u2713\u2714\u2716\u2718\u26a0\u2696\u2699\u2702\u2709\u270e\u270f\u260e\u2611\u2612\u2665\u2661\u2728\u2733\u2734\u2744\u2747\u274c\u274e\u2757\u2764\u2b50]')

html_path = ROOT / "index.html"
lines = html_path.read_text(encoding="utf-8").splitlines()

for i, line in enumerate(lines, 1):
    matches = list(EMOJI_PATTERN.finditer(line))
    if matches:
        escaped_line = line.encode('ascii', 'backslashreplace').decode('ascii')
        chars = [m.group().encode('ascii', 'backslashreplace').decode('ascii') for m in matches]
        print(f"L{i}: {' '.join(chars)} -> {escaped_line.strip()[:80]}")
