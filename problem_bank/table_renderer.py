# problem_bank/table_renderer.py
# - 다양한 PACK payload에서 "표"를 최대한 안정적으로 찾아서
#   Streamlit/Docx 쪽에서 공통으로 쓰기 위한 유틸 모듈
#
# ✅ 핵심: try_find_table(payload, keys)
#    - keys 후보들을 먼저 보고
#    - 없으면 payload 전체를 깊게 뒤져서(table-like) 오브젝트를 찾아냄
#
# ✅ normalize_table_to_grid(table_obj)
#    - 어떤 형태든 (headers, rows)로 정규화
#    - headers: List[str]
#    - rows   : List[List[Any]]  (각 row는 headers 길이에 맞춰 padding)

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# table-like 판별/추출 helpers
# ----------------------------
def _is_2d_list(x: Any) -> bool:
    """[[...], [...]] 형태(2차원 리스트)인지"""
    if not isinstance(x, list) or not x:
        return False
    if not all(isinstance(r, list) for r in x):
        return False
    # 너무 짧은 2D는 표로 보기 애매할 수 있지만, 일단 인정
    return True


def _looks_like_table_dict(d: Dict[str, Any]) -> bool:
    """
    dict가 표를 담는 구조인지 대충 판별
    - {headers: [...], rows: [[...], ...]}
    - {cols: [...], data: [[...], ...]}
    - {header: [...], body: [[...], ...]}
    - {grid: [[...], ...]} 등
    """
    if not isinstance(d, dict):
        return False

    # 대표 키 조합들
    pairs = [
        ("headers", "rows"),
        ("header", "rows"),
        ("cols", "rows"),
        ("columns", "rows"),
        ("headers", "data"),
        ("cols", "data"),
        ("columns", "data"),
        ("header", "data"),
        ("grid", None),
        ("table", None),
        ("matrix", None),
        ("cells", None),
    ]
    for a, b in pairs:
        if a in d:
            if b is None:
                v = d.get(a)
                if _is_2d_list(v):
                    return True
            else:
                v1, v2 = d.get(a), d.get(b)
                if isinstance(v1, list) and _is_2d_list(v2):
                    return True
    return False


def _extract_from_table_dict(d: Dict[str, Any]) -> Any:
    """
    table-like dict에서 실제 grid를 뽑아냄.
    반환은 가능한 한 "2D 리스트" 또는 "headers/rows tuple" 형태로 이어질 수 있게 함.
    """
    # 1) grid류
    for k in ("grid", "matrix", "cells"):
        v = d.get(k)
        if _is_2d_list(v):
            return v

    # 2) table 아래
    v = d.get("table")
    if _is_2d_list(v):
        return v

    # 3) headers/rows 또는 cols/data 조합
    for hk, rk in [
        ("headers", "rows"),
        ("header", "rows"),
        ("cols", "rows"),
        ("columns", "rows"),
        ("headers", "data"),
        ("cols", "data"),
        ("columns", "data"),
        ("header", "data"),
    ]:
        headers = d.get(hk)
        rows = d.get(rk)
        if isinstance(headers, list) and _is_2d_list(rows):
            # headers가 행/열 레이블을 포함할 수도 있으니 그냥 같이 넘김
            return {"headers": headers, "rows": rows}

    # 4) dict 자체가 row map일 수도 있음 (예: {"가":[...], "나":[...]})
    #    이 경우 normalize에서 처리할 수 있게 그대로 반환
    return d


def _deep_find_table(obj: Any, max_depth: int = 6, _depth: int = 0) -> Optional[Any]:
    """
    payload 안을 재귀적으로 뒤져서 table-like 오브젝트를 하나 찾아냄.
    - 너무 깊게 들어가면 속도/무한재귀 위험 -> max_depth 제한
    """
    if _depth > max_depth:
        return None

    # 1) 바로 2D list
    if _is_2d_list(obj):
        return obj

    # 2) dict면 table-like인지 확인
    if isinstance(obj, dict):
        if _looks_like_table_dict(obj):
            return _extract_from_table_dict(obj)

        # 흔한 wrapper 키 우선 탐색
        priority_keys = [
            "_given_table", "_full_table",
            "given_table", "masked_table", "full_table", "complete_table",
            "presented_table", "answer_table",
            "table", "grid", "matrix",
        ]
        for k in priority_keys:
            if k in obj:
                found = _deep_find_table(obj.get(k), max_depth=max_depth, _depth=_depth + 1)
                if found is not None:
                    return found

        # 그 외 모든 키 순회
        for v in obj.values():
            found = _deep_find_table(v, max_depth=max_depth, _depth=_depth + 1)
            if found is not None:
                return found
        return None

    # 3) list면 내부 원소들 탐색
    if isinstance(obj, list):
        for v in obj:
            found = _deep_find_table(v, max_depth=max_depth, _depth=_depth + 1)
            if found is not None:
                return found
        return None

    return None


# ----------------------------
# 외부에서 쓰는 "표 찾기" API
# ----------------------------
def try_find_table(payload: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    """
    payload에서 표 오브젝트를 찾아 반환.
    1) keys 후보를 순서대로 확인
    2) 없으면 payload 전체를 deep scan
    """
    if not isinstance(payload, dict):
        return None

    # 1) keys 우선
    for k in keys:
        if k in payload and payload[k] not in (None, "", [], {}):
            v = payload[k]
            # table-like dict면 grid 추출
            if isinstance(v, dict) and _looks_like_table_dict(v):
                return _extract_from_table_dict(v)
            return v

    # 2) deep scan
    return _deep_find_table(payload, max_depth=6)


# ----------------------------
# "표 정규화" API
# ----------------------------
def normalize_table_to_grid(table_obj: Any) -> Tuple[List[str], List[List[Any]]]:
    """
    table_obj를 (headers, rows) 형태로 변환.
    가능한 입력 형태:
    - 2D list: [ [h1,h2,...], [r1c1,r1c2,...], ... ]  (첫 행을 headers로 가정)
    - dict: {"headers":[...], "rows":[[...]...]} / {"cols":[...], "data":[[...]...]} / {"grid":[[...]...]} 등
    - dict(row_map): {"가":[...], "나":[...]} 형태도 지원(행 이름을 첫 열로 붙임)
    """
    # 0) None
    if table_obj is None:
        return ([""], [])

    # 1) 이미 {"headers":..., "rows":...} 형태
    if isinstance(table_obj, dict):
        # a) headers/rows 형태
        if "headers" in table_obj and "rows" in table_obj and isinstance(table_obj["headers"], list) and isinstance(table_obj["rows"], list):
            headers = [str(x) for x in table_obj["headers"]]
            rows_raw = table_obj["rows"]
            rows = [list(r) if isinstance(r, list) else [r] for r in rows_raw]
            return _pad_grid(headers, rows)

        # b) cols/data 형태
        if "cols" in table_obj and "data" in table_obj and isinstance(table_obj["cols"], list) and isinstance(table_obj["data"], list):
            headers = [str(x) for x in table_obj["cols"]]
            rows_raw = table_obj["data"]
            rows = [list(r) if isinstance(r, list) else [r] for r in rows_raw]
            return _pad_grid(headers, rows)

        if "columns" in table_obj and "data" in table_obj and isinstance(table_obj["columns"], list) and isinstance(table_obj["data"], list):
            headers = [str(x) for x in table_obj["columns"]]
            rows_raw = table_obj["data"]
            rows = [list(r) if isinstance(r, list) else [r] for r in rows_raw]
            return _pad_grid(headers, rows)

        # c) grid/matrix/cells/table
        for k in ("grid", "matrix", "cells", "table"):
            v = table_obj.get(k)
            if _is_2d_list(v):
                return normalize_table_to_grid(v)

        # d) row_map: {"가":[...], "나":[...]} 같은 형태
        #    -> 첫 열에 row key 붙이고, 가장 긴 row 기준으로 col headers 생성
        if table_obj and all(isinstance(v, (list, tuple)) for v in table_obj.values()):
            row_names = [str(k) for k in table_obj.keys()]
            row_vals = [list(v) for v in table_obj.values()]

            max_len = max((len(r) for r in row_vals), default=0)
            headers = [""] + [str(i + 1) for i in range(max_len)]
            rows: List[List[Any]] = []
            for name, vals in zip(row_names, row_vals):
                rows.append([name] + vals)
            return _pad_grid(headers, rows)

        # e) 마지막 fallback: dict 자체를 텍스트로
        return (["value"], [[str(table_obj)]])

    # 2) 2D list
    if _is_2d_list(table_obj):
        grid: List[List[Any]] = table_obj
        # 첫 행을 headers로 간주
        headers = [str(x) for x in grid[0]]
        rows = [list(r) for r in grid[1:]]
        # headers가 비어있으면 최소 1열 보장
        if not headers:
            headers = [""]
        return _pad_grid(headers, rows)
    if isinstance(table_obj, list):
        if all(isinstance(x, str) for x in table_obj):
            headers = ["항목"]
            rows = [[x] for x in table obj]
            return _pad_grid(headers, rows)
            
    # 3) 1D list: 한 줄짜리로 처리
    if isinstance(table_obj, list):
        headers = [str(i + 1) for i in range(len(table_obj))]
        rows = [list(table_obj)]
        return _pad_grid(headers, rows)

    # 4) str/number 등
    return (["value"], [[str(table_obj)]])


def _pad_grid(headers: List[str], rows: List[List[Any]]) -> Tuple[List[str], List[List[Any]]]:
    """행 길이를 headers에 맞춰 padding(빈칸)"""
    w = len(headers)
    out_rows: List[List[Any]] = []
    for r in rows:
        rr = list(r)
        if len(rr) < w:
            rr += [""] * (w - len(rr))
        elif len(rr) > w:
            rr = rr[:w]
        out_rows.append(rr)
    return headers, out_rows
