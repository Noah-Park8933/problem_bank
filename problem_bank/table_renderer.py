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
    if "rows" in d and _is_2d_list(d.get("rows")):
        return True
    if "data" in d and _is_2d_list(d.get("data")):
        return True
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
    if _is_2d_list(d.get("rows")):
        return {"headers": d.get("headers") or d.get("cols") or d.get("columns") or [], "rows": d["rows"]}
    if _is_2d_list(d.get("data")):
        return {"headers": d.get("headers") or d.get("cols") or d.get("columns") or [], "rows": d["data"]}

    
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
            "meta", "metadata", "history", "log", "choices", "choice", "options", "option",
            "보기", "선지", "선택지", "문항", "question_choices", "statements", "statement", "gnd", "stmts", "stmt", "ㄱ", "ㄴ", "ㄷ",
        }

        # 표 후보 우선 키 (given/문항표를 먼저 찾고, 그다음 일반 table)
        priority_keys = [
            "_given_table", "given_table", "masked_table", "presented_table",
            "problem_table", "table_data", "table_obj",
            "table_md", "full_table_md", "table", "grid", "matrix", "cells",
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
    우선순위:
      1) (table_md/full_table_md 등) markdown 표 문자열
      2) keys 후보(주어진 순서대로)
      3) payload 전체 deep scan (오탐 방어 포함)
    """
    if not isinstance(payload, dict):
        return None

    # 0) markdown table 키는 항상 최우선 (DNA integration 같은 케이스)
    md_keys = [
        "_given_table_md", "given_table_md", "table_md",
        "_full_table_md", "full_table_md",
    ]
    for k in md_keys:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            # normalize_table_to_grid()가 md 파싱을 지원하므로 문자열 그대로 반환
            return v

    # 1) keys 우선
    for k in keys:
        if k in payload and payload[k] not in (None, "", [], {}):
            v = payload[k]
            # table-like dict면 grid 추출
            if isinstance(v, dict) and _looks_like_table_dict(v):
                return _extract_from_table_dict(v)
            return v

    # 2) deep scan (gene detecting에서 stmts 같은 2D 오탐 방어는 _deep_find_table()의 skip_keys가 담당)
    found = _deep_find_table(payload, max_depth=6)

    # 2D가 너무 작은 경우(계산 매트릭스/선지 배열 등)는 표로 채택하지 않음
    if _is_2d_list(found):
        if len(found) < 3 or max(len(r) for r in found) < 3:
            return None

    return found


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

def _parse_md_table(md: str) -> Optional[List[List[str]]]:
    """
    GitHub style markdown table:
    | h1 | h2 |
    | --- | --- |
    | a | b |

    ✅ 개선:
    - md가 '### (가)
 ... 
| h1 | h2 | ...' 처럼
      표 앞뒤에 텍스트가 섞여 있어도 첫 번째 표 블록을 찾아 파싱한다.
    """
    if not isinstance(md, str):
        return None
    s = md.strip()
    if "|" not in s:
        return None

    # 공백 라인은 제외하고 전체 라인을 유지
    lines_all = [ln.rstrip() for ln in s.splitlines() if ln.strip()]
    if len(lines_all) < 2:
        return None

    def split_row(ln: str) -> List[str]:
        ln = ln.strip()
        if ln.startswith("|"):
            ln = ln[1:]
        if ln.endswith("|"):
            ln = ln[:-1]
        return [c.strip() for c in ln.split("|")]

    def is_sep_line(ln: str) -> bool:
        # | --- | :---: | ---: | 같은 구분선 판별
        cells = split_row(ln)
        if not cells:
            return False
        for c in cells:
            t = c.replace(":", "").replace("-", "").strip()
            if t != "":
                return False
        return True

    # ✅ 표 블록 시작점 찾기: header 다음 줄이 구분선이면 표 시작
    start = None
    for i in range(len(lines_all) - 1):
        if "|" not in lines_all[i]:
            continue
        if "|" not in lines_all[i + 1]:
            continue
        if is_sep_line(lines_all[i + 1]):
            start = i
            break

    if start is None:
        return None

    header = split_row(lines_all[start])

    # start+1 은 구분선, start+2부터 body
    rows = []
    for j in range(start + 2, len(lines_all)):
        ln = lines_all[j]
        # 표 블록 종료: '|'가 사라지면 다음 섹션 텍스트로 간주
        if "|" not in ln:
            break
        rows.append(split_row(ln))

    if not rows:
        return None

    return [header] + rows


def _parse_md_tables(md: str) -> List[List[List[str]]]:
    """
    md 문자열 안에서 markdown table 블록들을 '모두' 찾아서 grid 리스트로 반환.

    반환 형식:
      - tables: List[grid]
      - grid: [header_row] + body_rows
    """
    if not isinstance(md, str):
        return []
    s = md.strip()
    if "|" not in s:
        return []

    lines_all = [ln.rstrip() for ln in s.splitlines() if ln.strip()]
    if len(lines_all) < 2:
        return []

    def split_row(ln: str) -> List[str]:
        ln = ln.strip()
        if ln.startswith("|"):
            ln = ln[1:]
        if ln.endswith("|"):
            ln = ln[:-1]
        return [c.strip() for c in ln.split("|")]

    def is_sep_line(ln: str) -> bool:
        cells = split_row(ln)
        if not cells:
            return False
        for c in cells:
            t = c.replace(":", "").replace("-", "").strip()
            if t != "":
                return False
        return True

    tables: List[List[List[str]]] = []
    i = 0
    n = len(lines_all)

    while i < n - 1:
        if ("|" in lines_all[i]) and ("|" in lines_all[i + 1]) and is_sep_line(lines_all[i + 1]):
            header = split_row(lines_all[i])
            rows: List[List[str]] = []
            j = i + 2
            while j < n and ("|" in lines_all[j]):
                rows.append(split_row(lines_all[j]))
                j += 1
            if rows:
                tables.append([header] + rows)
            i = j
        else:
            i += 1

    return tables


def _grid_from_md_or_text(x: Any) -> Optional[Tuple[List[str], List[List[str]]]]:
    if not isinstance(x, str):
        return None
    grid = _parse_md_table(x)
    if grid is None:
        return None
    headers = ["" if v is None else str(v) for v in grid[0]]
    rows = [[("" if v is None else str(v)) for v in r] for r in grid[1:]]
    return _pad_grid(headers, rows)
def _smart_col_sort_key(x: Any):
    s = str(x).strip()

    # 1) 알파벳 1글자면: 같은 글자끼리 묶고(소문자 기준), 대문자 먼저
    if len(s) == 1 and s.isalpha():
        return (s.lower(), 0 if s.isupper() else 1)

    # 2) 그 외는 그냥 문자열 정렬
    return (s,)
    
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
    # 0) markdown table string
    md_parsed = _grid_from_md_or_text(table_obj)
    if md_parsed is not None:
        return md_parsed

    # 0-B) {'headers': [...], 'rows': [[...], ...]} 또는 {'cols': [...], 'rows': ...} 지원
    # ( _extract_from_table_dict() 가 이런 형태를 반환할 수 있음 )
    if isinstance(table_obj, dict) and "rows" in table_obj and _is_2d_list(table_obj.get("rows")):
        headers_raw = table_obj.get("headers") or table_obj.get("cols") or table_obj.get("columns") or []
        if isinstance(headers_raw, list) and headers_raw:
            headers = [("" if x is None else str(x)) for x in headers_raw]
        else:
            w = max((len(r) for r in table_obj["rows"]), default=1)
            headers = [f"c{i+1}" for i in range(w)]

        rows = []
        for r in table_obj["rows"]:
            r2 = [("" if x is None else str(x)) for x in (r or [])]
            rows.append(r2)
        return _pad_grid(headers, rows)
    # 1) nested dict: {row: {col: value}}
    if isinstance(table_obj, dict):
        if table_obj and all(isinstance(v, dict) for v in table_obj.values()):
            row_labels = list(table_obj.keys())

            col_set = set()
            for inner in table_obj.values():
                col_set.update(inner.keys())

            # 보기 좋게 정렬(문자열 기준)
            col_labels = sorted(col_set, key=_smart_col_sort_key)

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

        col_labels = sorted(col_set, key=_smart_col_sort_key)
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


def normalize_tables_to_grids(table_obj: Any) -> List[Tuple[List[str], List[List[str]]]]:
    """
    ✅ 복수 표 지원:
    - table_obj가 문자열이면, md 내부의 표를 여러 개 파싱해 (headers, rows) 리스트로 반환.
    - 그 외 타입이면 기존 normalize_table_to_grid 결과를 1개짜리 리스트로 반환.
    """
    if isinstance(table_obj, str):
        grids = _parse_md_tables(table_obj)
        out: List[Tuple[List[str], List[List[str]]]] = []
        for g in grids:
            headers = [("" if v is None else str(v)) for v in g[0]]
            rows = [[("" if v is None else str(v)) for v in r] for r in g[1:]]
            out.append(_pad_grid(headers, rows))
        # 문자열인데 표를 못 찾았으면 기존 단일 파서로라도 시도
        if out:
            return out
        h, r = normalize_table_to_grid(table_obj)
        return [(h, r)]

    h, r = normalize_table_to_grid(table_obj)
    return [(h, r)]
