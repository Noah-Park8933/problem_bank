import os, json, glob
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .config import AppConfig

@dataclass
class ProblemItem:
    pid: str           # PACK 내부 problem id
    module: str        # module_code
    prefix: str        # id_prefix
    path: str          # json file path
    payload: Dict[str, Any]

    @property
    def uid(self) -> str:
        # streamlit key 충돌 방지용(파일경로까지 포함)
        return f"{self.path}::{self.pid}"

def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # 일부 파일 깨짐 방어
        return None

def discover_pack_jsons(cfg: AppConfig) -> List[str]:
    paths: List[str] = []
    for d in cfg.data_dirs:
        if not os.path.exists(d):
            continue
        # pack_*.json / *.pack.json / *.json 다 탐색
        patterns = [
            os.path.join(d, "**", "*.json"),
        ]
        for ptn in patterns:
            paths.extend(glob.glob(ptn, recursive=True))
    # 너무 많으면 중복 제거
    uniq = sorted(set(paths))
    return uniq

def parse_pack(doc: Dict[str, Any], fallback_module: str, fallback_prefix: str) -> List[ProblemItem]:
    """
    PACK json 형태가 조금씩 달라도 최대한 읽어내는 파서.
    기대 형태(권장):
      {"module_code": "...", "id_prefix":"...", "problems":[{"pid":"...", "payload":{...}}, ...]}
    """
    module = str(doc.get("module_code") or doc.get("module") or fallback_module or "UNKNOWN")
    prefix = str(doc.get("id_prefix") or doc.get("prefix") or fallback_prefix or f"{module}_")

    probs = doc.get("problems") or doc.get("items") or doc.get("data") or []
    out: List[ProblemItem] = []

    if isinstance(probs, dict):
        # {"id": payload} 형태
        for k, v in probs.items():
            if isinstance(v, dict):
                out.append(ProblemItem(pid=str(k), module=module, prefix=prefix, path="", payload=v))
        return out

    if not isinstance(probs, list):
        return out

    for it in probs:
        if not isinstance(it, dict):
            continue
        pid = it.get("pid") or it.get("id") or it.get("problem_id")
        payload = it.get("payload") if isinstance(it.get("payload"), dict) else it
        if pid is None:
            # pid 없으면 payload에서 id 찾기
            pid = payload.get("id") if isinstance(payload, dict) else None
        if pid is None:
            continue
        out.append(ProblemItem(pid=str(pid), module=module, prefix=prefix, path="", payload=payload))
    return out

def load_all(cfg: AppConfig) -> List[ProblemItem]:
    json_paths = discover_pack_jsons(cfg)
    items: List[ProblemItem] = []

    for p in json_paths:
        doc = _read_json(p)
        if doc is None:
            continue

        # pack 형태가 아니고 "problem 단일 json"일 수도 있어서 처리
        if isinstance(doc, dict) and ("problems" in doc or "module_code" in doc or "id_prefix" in doc):
            parsed = parse_pack(doc, fallback_module=os.path.basename(p), fallback_prefix="")
            for it in parsed:
                it.path = p
                items.append(it)
        else:
            # 단일 문제 json이라 가정
            pid = None
            if isinstance(doc, dict):
                pid = doc.get("pid") or doc.get("id") or doc.get("problem_id")
            if pid is None:
                continue
            module = str(doc.get("module_code") or doc.get("module") or "SINGLE")
            prefix = str(doc.get("id_prefix") or f"{module}_")
            items.append(ProblemItem(pid=str(pid), module=module, prefix=prefix, path=p, payload=doc))

        if len(items) >= cfg.max_load:
            break

    return items