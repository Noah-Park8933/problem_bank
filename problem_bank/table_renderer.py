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

def normalize_table_to_grid(table_obj):
    """
    table_obj가 어떤 형태든
    (headers, rows) 형태로 표준화.

    headers = ["", c1, c2, c3, ...]
    rows = [
        [r1, v11, v12, v13, ...],
        [r2, v21, v22, v23, ...],
        ...
    ]

    ※ XY 축 반전 문제를 방지하기 위해
      - row_map은 rows로
      - col_map은 columns로 확정
      순서를 절대 바꾸지 않는다.
    """
    # 1) row_map + col_map 형태
    if isinstance(table_obj, dict):
        rmap = table_obj.get("row_map")
        cmap = table_obj.get("col_map")
        grid  = table_obj.get("grid") or table_obj.get("table") or table_obj.get("values")

        if rmap and cmap and grid:
            headers = [""] + list(cmap)
            rows = []

            for r_idx, rname in enumerate(rmap):
                row = [rname] + list(grid[r_idx])
                rows.append(row)

            return headers, rows

    # 2) 2D 배열 형태 (fallback)
    if isinstance(table_obj, list) and table_obj and isinstance(table_obj[0], list):
        headers = [""] + [f"C{i}" for i in range(1, len(table_obj[0])+1)]
        rows = []
        for idx, line in enumerate(table_obj):
            rows.append([f"R{idx+1}"] + list(line))
        return headers, rows

    # 3) 문자열 fallback
    return ["표"], [["인식 불가", str(table_obj)]]
