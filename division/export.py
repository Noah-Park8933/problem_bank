# division_pack/export.py
from __future__ import annotations

import json
from typing import Any, Dict

def save_pack(pack: Dict[str, Any], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)
