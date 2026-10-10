import re
from pathlib import Path

ROOT = Path(r"c:\Users\manid\Documents\cube-round3-pod-3\orchestration\static")

EMOJI_PATTERN = re.compile(r'[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\ufe00-\ufe0f\u200d\u25b2\u25bc\u2605\u2606\u2713\u2714\u2716\u2718\u26a0\u2696\u2699\u2702\u2709\u270e\u270f\u260e\u2611\u2612\u2665\u2661\u2728\u2733\u2734\u2744\u2747\u274c\u274e\u2757\u2764\u2b50]')

files_to_check = [
    ROOT / "index.html",
    ROOT / "scanner.html",
    ROOT / "scanner.js",
    ROOT / "cockpit.js",
    ROOT / "styles.css",
]

total_found = 0
for f in files_to_check:
    if not f.exists():
        continue
    content = f.read_text(encoding="utf-8")
    matches = list(EMOJI_PATTERN.finditer(content))
    print(f"{f.name}: {len(matches)} emojis/symbols found")
    total_found += len(matches)
    for m in matches[:15]:
        line_num = content[:m.start()].count('\n') + 1
        val = m.group().encode('ascii', 'backslashreplace').decode('ascii')
        print(f"  Line {line_num}: {val}")

print(f"\nTotal: {total_found}")
