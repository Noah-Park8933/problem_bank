import os, json, glob
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .config import AppConfig


# ---------------------------------------------------
# ProblemItem
# ---------------------------------------------------
import hashlib
import json

@dataclass
class ProblemItem:
    pid: str
    module: str
    prefix: str
    path: str
    payload: Dict[str, Any]

    @property
    def uid(self) -> str:
        """
        내용 기반 uid (같은 문제는 파일 경로가 달라도 uid가 동일)
        - payload에서 uid에 반영할 핵심만 추려서 안정적으로 해시
        """
        # 1) payload에서 '변해도 상관없는 값'은 제거(있다면)
        #    예: 생성시간, path, internal id, random seed 등
        p = dict(self.payload)

        for k in ["generated_at", "timestamp", "path", "file_path", "uid"]:
            if k in p:
                p.pop(k, None)

        # 2) 안정적 직렬화 후 해시
        s = json.dumps(p, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]

        # 3) module/prefix까지 섞으면 다른 모듈 간 충돌도 방지
        return f"{self.module}:{self.prefix}:{h}"


# ---------------------------------------------------
# 기본 JSON reader
# ---------------------------------------------------
def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------
# 데이터 디렉토리 내의 .json 파일 자동 검색
# ---------------------------------------------------
def discover_pack_jsons(cfg: AppConfig) -> List[str]:
    paths: List[str] = []
    for d in cfg.data_dirs:
        if not os.path.exists(d):
            continue

        patterns = [
            os.path.join(d, "**", "*.json"),
        ]

        for ptn in patterns:
            paths.extend(glob.glob(ptn, recursive=True))

    uniq = sorted(set(paths))
    return uniq


# ---------------------------------------------------
# 여러 후보 키 중 "첫 번째로 존재하는 것" 찾기
# ---------------------------------------------------
def _pick_first(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return None


# ---------------------------------------------------
# 표 키를 `_given_table`, `_full_table` 로 통일
# ---------------------------------------------------
def normalize_tables(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload

    given = _pick_first(payload, [
        "_given_table",
        "given_table", "masked_table", "presented_table",
        "table", "problem_table", "masked",
        "table_obj", "table_data", "table2"
    ])

    full = _pick_first(payload, [
        "_full_table",
        "full_table", "complete_table", "answer_table",
        "solution_table", "filled_table",
        "full", "complete"
    ])

    if given is not None:
        payload["_given_table"] = given
    if full is not None:
        payload["_full_table"] = full

    return payload
def normalize_images(payload):
    if not isinstance(payload, dict):
        return payload

    for k in ["image", "img", "image_path", "tree_img", "figure", "fig", "diagram_image"]:
        if k in payload and isinstance(payload[k], str) and payload[k].strip():
            payload["_image_path"] = payload[k].strip()
            break

    return payload


# ---------------------------------------------------
# PACK JSON 파서(핵심)
# ---------------------------------------------------
def parse_pack(doc: Dict[str, Any], fallback_module: str, fallback_prefix: str) -> List[ProblemItem]:
    """
    다양한 형태의 PACK JSON을 최대한 읽어내는 파서
    """
    module = str(doc.get("module_code") or doc.get("module") or fallback_module or "UNKNOWN")
    prefix = str(doc.get("id_prefix") or doc.get("prefix") or fallback_prefix or f"{module}_")

    probs = (
        doc.get("problems")
        or doc.get("items")
        or doc.get("data")
        or doc.get("list")
        or doc.get("entries")
        or []
    )

    out: List[ProblemItem] = []

    # dict 형태 { "id" : payload }
    if isinstance(probs, dict):
        for k, v in probs.items():
            if isinstance(v, dict):
                v = normalize_tables(v)
                out.append(ProblemItem(pid=str(k), module=module, prefix=prefix, path="", payload=v))
        return out

    # 리스트가 아니면 종료
    if not isinstance(probs, list):
        return out

    # 리스트 형태의 문제들 처리
    for it in probs:
        if not isinstance(it, dict):
            continue

        # pid 후보
        pid = (
            it.get("pid")
            or it.get("id")
            or it.get("problem_id")
            or it.get("problem_code")
            or it.get("problem__code")   # 혹시나
            or it.get("code")
        )

        # payload 처리
        raw = it.get("payload", None)

        if isinstance(raw, dict):
            inner = raw
        elif isinstance(raw, list):
            inner = {"table": raw}
        elif isinstance(raw, str):
            inner = {"text": raw}
        else:
            inner = {}

        payload = dict(inner)
        payload = normalize_tables(payload)
        payload = normalize_images(payload)
        # item-level 메타 병합
        for k, v in it.items():
            if k == "payload":
                continue
            if v not in (None, "", [], {}):
                # payload에 없거나 빈 값이면 채우는 방식
                if k not in payload or payload[k] in (None, "", [], {}):
                    payload[k] = v

        # module/prefix 보완
        payload.setdefault("module", module)
        payload.setdefault("id_prefix", prefix)

        # pid 최종 확보
        if pid is None:
            pid = (
                payload.get("pid")
                or payload.get("id")
                or payload.get("problem_id")
                or payload.get("problem_code")
            )

        if pid is None:
            continue

        out.append(ProblemItem(pid=str(pid), module=module, prefix=prefix, path="", payload=payload))

    return out


# ---------------------------------------------------
# 모든 PACK JSON 로드
# ---------------------------------------------------
def load_all(cfg: AppConfig) -> List[ProblemItem]:
    json_paths = discover_pack_jsons(cfg)
    items: List[ProblemItem] = []

    for p in json_paths:
        doc = _read_json(p)
        if doc is None:
            continue

        # PACK JSON
        if isinstance(doc, dict) and ("problems" in doc or "items" in doc or "module_code" in doc or "id_prefix" in doc):
            parsed = parse_pack(doc, fallback_module=os.path.basename(p), fallback_prefix="")
            for it in parsed:
                it.path = p
                items.append(it)
            continue

        # 단일 문제 JSON
        if isinstance(doc, dict):
            pid = doc.get("pid") or doc.get("id") or doc.get("problem_id")
            if pid is None:
                continue

            module = str(doc.get("module_code") or doc.get("module") or "SINGLE")
            prefix = str(doc.get("id_prefix") or f"{module}_")

            doc = normalize_tables(doc)
            items.append(ProblemItem(pid=str(pid), module=module, prefix=prefix, path=p, payload=doc))

    return dedupe_items(items)


def load_one_pack(pack_path: str) -> List[ProblemItem]:
    doc = _read_json(pack_path)
    if not isinstance(doc, dict):
        return []

    parsed = parse_pack(doc, fallback_module=os.path.basename(pack_path), fallback_prefix="")
    for it in parsed:
        it.path = pack_path
    return parsed
def dedupe_items(items: List[ProblemItem]) -> List[ProblemItem]:
    seen = set()
    out = []
    for it in items:
        k = it.uid  # path::pid
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out

