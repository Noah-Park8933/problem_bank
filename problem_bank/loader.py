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
def _pick_first(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return None

def normalize_tables(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    각 생성기마다 제시표/완성표 키가 달라도
    웹에서는 _given_table / _full_table만 보면 되도록 통일.
    """
    if not isinstance(payload, dict):
        return payload

    # 1) 제시표(문제에 보여주는 표) 후보 키들
    given = _pick_first(payload, [
        "_given_table",
        "given_table", "masked_table", "presented_table",
        "table", "problem_table", "masked",
        "table_obj", "table_data",
    ])

    # 2) 완성표(정답/해설에 넣을 표) 후보 키들
    full = _pick_first(payload, [
        "_full_table",
        "full_table", "complete_table", "answer_table",
        "solution_table", "filled_table",
        "full", "complete",
    ])

    if given is not None:
        payload["_given_table"] = given
    if full is not None:
        payload["_full_table"] = full

    return payload

def parse_pack(doc: Dict[str, Any], fallback_module: str, fallback_prefix: str) -> List[ProblemItem]:
    """
    PACK json 형태가 조금씩 달라도 최대한 읽어내는 파서.
    기대 형태(권장):
      {"module_code": "...", "id_prefix":"...", "problems":[{"pid":"...", "payload":{...}}, ...]}
    """
    module = str(doc.get("module_code") or doc.get("module") or fallback_module or "UNKNOWN")
    prefix = str(doc.get("id_prefix") or doc.get("prefix") or fallback_prefix or f"{module}_")

    probs = doc.get("problems") or doc.get("items") or doc.get("data") or doc.get("list") or doc.get("entries") or []
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
        pid = it.get("pid") or it.get("id") or it.get("problem_id") or it.get("problem__code") or None
        raw
        raw = it.get("payload") 
            if isinstance(raw, dict) : 
                inner raw 
            elif isinstance(raw, list) : 
                inner = {"table" : raw}
            elif isinstance(raw, str) : 
                inner = {"text" : raw}
            else : 
                inner = {}
            payload normalize_table(inner)
        payload = dict(inner)  # inner가 우선
        payload = normalize_tables(payload)
        # item-level 메타도 같이 싣기(빈 값은 덮어쓰지 않게)
        for k, v in it.items():
            if k == "payload":
                continue
            if k not in payload or payload.get(k) in (None, "", [], {}):
                payload[k] = v

# (선택) 모듈/프리픽스도 payload에 확실히 넣어두면 웹에서 분류가 편함
        payload.setdefault("module", module)
        payload.setdefault("id_prefix", prefix)

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
            doc = normalize_tables(doc)
            items.append(ProblemItem(pid=str(pid), module=module, prefix=prefix, path=p, payload=doc))

      #  if len(items) >= cfg.max_load:
       #     break

    return items
