from typing import Any, Dict, List, Optional, Tuple

def is_table_like(obj: Any) -> bool:
    # dict-of-dict (cell->gene) or list-of-lists 등
    if isinstance(obj, dict):
        # 값들이 dict/list/str 가능
        return True
    if isinstance(obj, list):
        return len(obj) > 0
    return False

def try_find_table(payload: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for k in keys:
        if k in payload and payload[k] is not None:
            return payload[k]
    # payload 내부에 table 후보가 숨어있을 수 있어서 1-depth 스캔
    for k, v in payload.items():
        if isinstance(v, dict) and any(kk in v for kk in keys):
            for kk in keys:
                if kk in v and v[kk] is not None:
                    return v[kk]
    return None

def normalize_table_to_grid(obj: Any) -> Tuple[List[str], List[List[str]]]:
    """
    다양한 table 형태를 "열 헤더 + 행 리스트"로 정규화.
    반환: (col_headers, rows) where rows[i] = [row_header, ...cells...]
    """
    # 1) dict-of-dict: {col:{row:val}} or {row:{col:val}}
    if isinstance(obj, dict):
        # dict-of-dict인지 확인
        if all(isinstance(v, dict) for v in obj.values()):
            outer_keys = list(obj.keys())
            inner_keys_set = set()
            for v in obj.values():
                inner_keys_set.update(list(v.keys()))
            inner_keys = list(inner_keys_set)

            # 두 방향 다 시도해보고 더 “균형 있는” 쪽 선택
            # A) outer=cols, inner=rows
            gridA = []
            for r in inner_keys:
                row = [str(r)]
                for c in outer_keys:
                    row.append(str(obj.get(c, {}).get(r, "")))
                gridA.append(row)

            # B) outer=rows, inner=cols
            gridB = []
            for r in outer_keys:
                row = [str(r)]
                for c in inner_keys:
                    row.append(str(obj.get(r, {}).get(c, "")))
                gridB.append(row)

            # 더 직사각형에 가까운 쪽을 선택(빈칸 적은 쪽)
            def empties(g):
                return sum(1 for row in g for x in row[1:] if x == "")

            if empties(gridA) <= empties(gridB):
                return [""] + [str(c) for c in outer_keys], gridA
            else:
                return [""] + [str(c) for c in inner_keys], gridB

        # 그냥 dict이면 key-value를 2열 표로
        headers = ["key", "value"]
        rows = [[str(k), str(v)] for k, v in obj.items()]
        return headers, rows

    # 2) list-of-lists
    if isinstance(obj, list):
        if len(obj) == 0:
            return ["(empty)"], []
        if all(isinstance(x, list) for x in obj):
            # 첫 줄을 헤더로 볼지 판단: 길이가 일정하면 그냥 그대로
            maxlen = max(len(r) for r in obj)
            rows = []
            for r in obj:
                rr = [str(x) for x in r] + [""] * (maxlen - len(r))
                rows.append(rr)
            headers = [f"c{i+1}" for i in range(maxlen)]
            return headers, rows
        # list of scalars
        return ["value"], [[str(x)] for x in obj]

    # 3) scalar
    return ["value"], [[str(obj)]]