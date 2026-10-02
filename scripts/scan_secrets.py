"""Scan the artefacts that are about to be committed for credential material.

The run records embed whatever the tools returned, so this checks for bearer
tokens, JWTs and API-key headers before anything reaches git history.
"""

import pathlib
import re

PATTERNS = {
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
    "bearer": re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    "apikey_header": re.compile(r"x-apikey\s*[:=]\s*[A-Za-z0-9]{8,}",
                                re.IGNORECASE),
    # Only flag a 32-hex blob when it is assigned to a key-like name. A bare
    # match also hits Web IQ trace ids and place ids inside result URLs, which
    # are not secrets and were drowning out real findings.
    "azure_key": re.compile(
        r"(?:api[_-]?key|subscription[_-]?key|secret|password)"
        r"\W{0,4}[a-f0-9]{32}\b", re.IGNORECASE),
}

hits = 0
for path in sorted(pathlib.Path(".").rglob("*")):
    if not path.is_file():
        continue
    if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
        continue
    if path.suffix not in {".json", ".md", ".py", ".log", ".txt"}:
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    for label, pattern in PATTERNS.items():
        match = pattern.search(text)
        if match:
            hits += 1
            print(f"{label:14} {path}  near offset {match.start()}")

print("clean" if not hits else f"{hits} potential secrets -- do not commit")
