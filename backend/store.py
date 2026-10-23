"""data/config.json: kayıtlı ampuller, kullanıcı sahneleri, kurulum token'ları."""
import json
import os
from pathlib import Path

DEFAULT = {"devices": [], "scenes": [], "tokens": {}}


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.data = {**DEFAULT, **json.loads(path.read_text(encoding="utf-8"))} if path.exists() else json.loads(json.dumps(DEFAULT))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)  # yarım yazılmış dosya bırakmaz
