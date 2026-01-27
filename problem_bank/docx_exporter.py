from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from docx.shared import Pt
from docx.enum.section import WD_ORIENTATION

from .loader import ProblemItem
from .table_renderer import normalize_table_to_grid, try_find_table
from .config import AppConfig

def _add_par(doc_or_cell, text: str, bold: bool=False):
    p = doc_or_cell.add_paragraph(text)
    if p.runs:
        p.runs[0].bold = bold
    return p

def _add_grid_table(doc_or_cell, table_obj: Any):
    headers, rows = normalize_table_to_grid(table_obj)
    t = doc_or_cell.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"

    for j, h in enumerate(headers):
        t.rows[0].cells[j].text = str(h)

    for i, r in enumerate(rows):
        for j in range(len(headers)):
            val = r[j] if j < len(r) else ""
            t.rows[i+1].cells[j].text = str(val)

def export_docx_bytes(
    cfg: AppConfig,
    selected: List[ProblemItem],
    include_explanations: bool = True,
    include_full_table: bool = True,
    two_columns: bool = True,
) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "바탕"
    style.font.size = Pt(9)

    # 2단은 Word “열”기능이 파이썬-docx에서 제약이 많아서
    # 우리가 계속 쓰던 방식: 1행 2열 테이블로 페이지당 2문항 구현
    idx = 0
    pnum = 1
    while idx < len(selected):
        if two_columns:
            outer = doc.add_table(rows=1, cols=2)
            left = outer.rows[0].cells[0]
            right = outer.rows[0].cells[1]
            targets = [(left, selected[idx], pnum)]
            idx += 1; pnum += 1
            if idx < len(selected):
                targets.append((right, selected[idx], pnum))
                idx += 1; pnum += 1
        else:
            targets = [(doc, selected[idx], pnum)]
            idx += 1; pnum += 1

        for container, it, num in targets:
            payload = it.payload or {}
            _add_par(container, f"[문제 {num}]  ID: {it.pid}  ({it.prefix})", bold=True)

            # 본문/요구사항
            ptxt = first_text(payload, cfg.problem_text_keys)
            atxt = first_text(payload, cfg.ask_line_keys)
            if ptxt:
                _add_par(container, "문제", bold=True); _add_par(container, ptxt)
            if atxt:
                _add_par(container, "요구사항", bold=True); _add_par(container, atxt)

            # 제시표(가능하면 표로)
            given = try_find_table(payload, list(cfg.given_table_keys))
            if given is not None:
                _add_par(container, "제시표", bold=True)
                _add_grid_table(container, given)

            _add_par(container, "")

        if idx < len(selected):
            doc.add_page_break()

    # 뒤에 정답/해설 몰아넣기
    doc.add_page_break()
    _add_par(doc, "[정답/해설]", bold=True)

    for i, it in enumerate(selected, start=1):
        payload = it.payload or {}
        _add_par(doc, f"{i}. ID: {it.pid}  ({it.prefix})", bold=True)

        ans = first_text(payload, cfg.answer_keys)
        expl = first_text(payload, cfg.explanation_keys)

        _add_par(doc, "정답", bold=True); _add_par(doc, ans or "(없음)")

        if include_full_table:
            full = try_find_table(payload, list(cfg.full_table_keys))
            if full is not None:
                _add_par(doc, "완성표", bold=True)
                _add_grid_table(doc, full)

        if include_explanations:
            _add_par(doc, "해설", bold=True)
            _add_par(doc, expl or "(없음)")

        _add_par(doc, "-" * 40)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()

def first_text(payload: Dict[str, Any], keys: Tuple[str, ...] | List[str]) -> Optional[str]:
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None