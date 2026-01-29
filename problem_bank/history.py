# history.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
import hashlib


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class ExportRecord:
    uid: str                 # item.uid (path::pid)
    pid: str
    module: str
    pack_path: str
    exported_at: str         # ISO timestamp
    docx_name: str           # download filename or saved filename
    docx_path: str           # saved path if exists, else ""
    sha256: str              # bytes hash (for uniqueness)
    meta: Dict[str, Any]


class HistoryStore:
    """
    Export(=DOCX 추출)된 문항만 기록하는 히스토리.
    - JSON 파일로 저장(앱 재시작해도 유지)
    - 동일 uid가 다시 export되면 last_export 갱신(덮어쓰기)
    """
    def __init__(self, json_path: str):
        self.json_path = json_path
        self._loaded = False
        self._data: Dict[str, ExportRecord] = {}

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        if not os.path.exists(self.json_path):
            self._data = {}
            return

        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            self._data = {}
            return

        items = raw.get("items", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
        out: Dict[str, ExportRecord] = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            uid = str(it.get("uid", "")).strip()
            if not uid:
                continue
            out[uid] = ExportRecord(
                uid=uid,
                pid=str(it.get("pid", "")),
                module=str(it.get("module", "")),
                pack_path=str(it.get("pack_path", "")),
                exported_at=str(it.get("exported_at", "")),
                docx_name=str(it.get("docx_name", "")),
                docx_path=str(it.get("docx_path", "")),
                sha256=str(it.get("sha256", "")),
                meta=dict(it.get("meta", {})) if isinstance(it.get("meta", {}), dict) else {},
            )
        self._data = out

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.json_path) or ".", exist_ok=True)
        payload = {"items": [asdict(r) for r in self.list_records()]}
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def add_export(
        self,
        *,
        uid: str,
        pid: str,
        module: str,
        pack_path: str,
        docx_name: str,
        docx_bytes: bytes,
        docx_path: str = "",
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.load()
        meta = meta or {}
        ts = now_iso()
        sha = hashlib.sha256(docx_bytes).hexdigest()

        prev = self._data.get(uid)
        if prev is None:
            self._data[uid] = ExportRecord(
                uid=uid,
                pid=pid,
                module=module,
                pack_path=pack_path,
                exported_at=ts,
                docx_name=docx_name,
                docx_path=docx_path,
                sha256=sha,
                meta=meta,
            )
        else:
            prev.exported_at = ts
            prev.docx_name = docx_name
            prev.docx_path = docx_path
            prev.sha256 = sha
            merged = dict(prev.meta)
            merged.update(meta)
            prev.meta = merged

        self.save()

    def was_exported(self, uid: str) -> bool:
        self.load()
        return uid in self._data

    def get(self, uid: str) -> Optional[ExportRecord]:
        self.load()
        return self._data.get(uid)

    def list_records(self) -> List[ExportRecord]:
        self.load()
        items = list(self._data.values())
        items.sort(key=lambda r: r.exported_at or "", reverse=True)
        return items

    def clear(self) -> None:
        self.load()
        self._data = {}
        self.save()
