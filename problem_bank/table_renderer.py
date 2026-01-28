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
def _looks_like_header_row(row: List[Any], other_rows: List[List[Any]]) -> bool:
    """첫 행이 헤더처럼 보이는지 대충 판별"""
    if not row:
        return False

    # 1) 첫 칸이 비어있고(좌상단 공백), 나머지 행들의 첫 칸이 대체로 비어있지 않으면 헤더 확률↑
    first_cell = "" if row[0] is None else str(row[0]).strip()
    if first_cell == "" and other_rows:
        nonempty_first_col = 0
        for r in other_rows[:5]:
            if len(r) == 0:
                continue
            c0 = "" if r[0] is None else str(r[0]).strip()
            if c0 != "":
                nonempty_first_col += 1
        if nonempty_first_col >= 2:
            return True

    # 2) 첫 행이 "텍스트 비율"이 높고, 다른 행들은 숫자/기호(?, 0, 1 등) 비율이 높으면 헤더 확률↑
    def is_texty(x: Any) -> bool:
        s = "" if x is None else str(x).strip()
        if s == "":
            return False
        # 숫자/기호 위주면 텍스트로 안 봄
        return not all(ch.isdigit() or ch in ".-+?/×÷=" for ch in s)

    texty = sum(is_texty(x) for x in row)
    if texty >= max(2, len(row) // 2):
        return True

    return False

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
    if _depth > max_depth:
        return None

    # ✅ 0) dict에서 "표가 있을 법한 키"를 먼저 강하게 탐색
    if isinstance(obj, dict):
        # ✅ deep scan에서 자주 오탐 나는 키들(해설/정답/솔루션/metadata 등) 제외
        skip_keys = {
            "solution", "solutions", "explanation", "commentary", "analysis",
            "answer", "answers", "full_table", "_full_table", "answer_table",
            "meta", "metadata", "history", "log",
        }

        # 표 후보 우선 키 (given/문항표를 먼저 찾고, 그다음 일반 table)
        priority_keys = [
            "_given_table", "given_table", "masked_table", "presented_table",
            "problem_table", "table_data", "table_obj",
            "table", "grid", "matrix", "cells",
        ]

        for k in priority_keys:
            if k in obj and k not in skip_keys:
                found = _deep_find_table(obj.get(k), max_depth=max_depth, _depth=_depth + 1)
                if found is not None:
                    return found

        # 그 외 키 순회 (skip 적용)
        for k, v in obj.items():
            if k in skip_keys:
                continue
            found = _deep_find_table(v, max_depth=max_depth, _depth=_depth + 1)
            if found is not None:
                return found
        return None

    # ✅ 1) 2D list는 "진짜 마지막에"만 인정 (오탐 방지)
    if _is_2d_list(obj):
        return obj

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
from typing import Any, List, Tuple

def _pad_grid(headers: List[str], rows: List[List[str]]) -> Tuple[List[str], List[List[str]]]:
    """행 길이/열 길이 불일치 방어"""
    if not headers:
        headers = [""]
    w = len(headers)
    out_rows: List[List[str]] = []
    for r in rows:
        r2 = list(r)
        if len(r2) < w:
            r2 += [""] * (w - len(r2))
        elif len(r2) > w:
            r2 = r2[:w]
        out_rows.append(r2)
    return headers, out_rows


def normalize_table_to_grid(table_obj: Any) -> Tuple[List[str], List[List[str]]]:
    """
    다양한 표 형태를 (headers, rows) 2D grid로 통일.
    - headers: 1행(열 이름)
    - rows: 본문 행들(각 행은 headers 길이에 맞춤)
    지원:
      1) nested dict: {row: {col: value}}
      2) list of dict: [{"row":..., "E":..., ...}, ...]
      3) 2D list/tuple: [["", "E", ...], ["가", "?", ...], ...]
      4) fallback: 문자열 1셀 표
    """

    # 1) nested dict: {row: {col: value}}
    if isinstance(table_obj, dict):
        if table_obj and all(isinstance(v, dict) for v in table_obj.values()):
            row_labels = list(table_obj.keys())

            col_set = set()
            for inner in table_obj.values():
                col_set.update(inner.keys())

            # 보기 좋게 정렬(문자열 기준)
            col_labels = sorted(col_set, key=lambda x: str(x))

            headers = ["세포"] + [str(c) for c in col_labels]
            rows: List[List[str]] = []
            for r in row_labels:
                inner = table_obj.get(r, {})
                row = [str(r)]
                for c in col_labels:
                    v = inner.get(c, "")
                    row.append("" if v is None else str(v))
                rows.append(row)

            return _pad_grid(headers, rows)

        # dict지만 nested가 아니면 key-value 나열 표로
        headers = ["key", "value"]
        rows = [[str(k), "" if v is None else str(v)] for k, v in table_obj.items()]
        return _pad_grid(headers, rows)

    # 2) list of dict
    if isinstance(table_obj, list) and table_obj and all(isinstance(x, dict) for x in table_obj):
        # row name 후보 키
        row_key_candidates = ["row", "행", "label", "name", "세포"]
        row_key = None
        for k in row_key_candidates:
            if k in table_obj[0]:
                row_key = k
                break

        # 모든 컬럼 합치기
        col_set = set()
        for d in table_obj:
            col_set.update(d.keys())
        if row_key and row_key in col_set:
            col_set.remove(row_key)

        col_labels = sorted(col_set, key=lambda x: str(x))
        headers = (["세포"] if row_key else ["idx"]) + [str(c) for c in col_labels]

        rows: List[List[str]] = []
        for i, d in enumerate(table_obj):
            rowname = str(d.get(row_key, i)) if row_key else str(i)
            row = [rowname]
            for c in col_labels:
                v = d.get(c, "")
                row.append("" if v is None else str(v))
            rows.append(row)

        return _pad_grid(headers, rows)

    # 3) 2D list/tuple
    if isinstance(table_obj, (list, tuple)):
        # 빈 리스트
        if len(table_obj) == 0:
            return ["(empty)"], [[""]]

        # 2D로 보이면 그대로
        if all(isinstance(r, (list, tuple)) for r in table_obj):
            grid = [list(r) for r in table_obj]
            # 첫 행을 headers로 가정
            first = grid[0]
            rest = grid[1:]
            if _looks_like_header_row(first, rest):
                headers = ["" if x is None else str(x) for x in first]
                rows = [[("" if x is None else str(x)) for x in r] for r in rest]
                return _pad_grid(headers, rows)
            # ✅ 헤더가 아닌 경우: 자동 헤더 생성 + 모든 행 유지
            width = max(len(r) for r in grid) if grid else 1
            headers = [f"c{i+1}" for i in range(width)]
            rows =   []
            for r in grid:
                r2 = [("" if x is None else str(x)) for x in r]
                if len(r2) < width:
                    r2 += [""] * (width - len(r2))
                else:
                    r2 = r2[:width]
                rows.append(r2)
            return _pad_grid(headers, rows)


        # 1D list면 한 열로
        headers = ["value"]
        rows = [[("" if x is None else str(x))] for x in table_obj]
        return _pad_grid(headers, rows)

    # 4) fallback: 그냥 문자열 1셀 표
    headers = ["value"]
    rows = [[("" if table_obj is None else str(table_obj))]]
    return _pad_grid(headers, rows)
