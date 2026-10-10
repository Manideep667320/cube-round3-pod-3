import re
from pathlib import Path

INDEX_PATH = Path(r"c:\Users\manid\Documents\cube-round3-pod-3\orchestration\static\index.html")
COCKPIT_PATH = Path(r"c:\Users\manid\Documents\cube-round3-pod-3\orchestration\static\cockpit.js")

# Let's inspect index.html text
content = INDEX_PATH.read_text(encoding="utf-8")
print(f"Original index.html length: {len(content)}")
