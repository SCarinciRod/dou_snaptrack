"""
Persistent deduplication state (JSONL of hashes).
Used to avoid reprocessing same items across runs.
"""

from __future__ import annotations

import json
from pathlib import Path


class DedupState:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._loaded = False
        self._seen: set[str] = set()

    def load(self):
        if self._loaded:
            return
        if self.path.exists():
            try:
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    try:
                        obj = json.loads(line)
                        h = obj.get("hash")
                        if h:
                            self._seen.add(h)
                    except Exception:
                        continue
            except Exception:
                pass
        self._loaded = True

    def has(self, h: str) -> bool:
        self.load()
        return h in self._seen

    def add(self, h: str):
        self.load()
        if h in self._seen:
            return
        self._seen.add(h)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"hash": h}, ensure_ascii=False) + "\n")
        except Exception:
            pass
