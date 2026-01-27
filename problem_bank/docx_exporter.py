# docx_exporter.py

import os
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .loader import ProblemItem
from .table_renderer import normalize_table_to_grid, try_find_table
from .config import AppConfig
import Cm

def _add_par(doc_or_cell, text: str, bold: bool = False):
    """문단 간격/줄간격을 타이트하게 고정해서 DOCX가 덜 지저분해지게."""
    p = doc_or_cell.add_paragraph()
    run = p.add_run(text)
    run.bold = bold

    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    return p


def _add_grid_table(doc_or_cell, table_obj: Any, total_width_in: float = 3.2):
    """
    table_obj를 '진짜 docx table'로 렌더.
    - 가장 중요: autofit 끄고(col 폭 고정) -> 표가 안 찌그러짐
    - 셀 문단 간격/줄간격 줄임
    """
    headers, rows = normalize_table_to_grid(table_obj)

    n_cols = max(1, len(headers))
    n_rows = 1 + len(rows)

    t = doc_or_cell.add_table(rows=n_rows, cols=n_cols)
    t.style = "Table Grid"
    # 열 너비 고정
    for col in range(n_cols):
        for row in range(n_rows):
            t.rows[row].cells[col].width = Cm(1.2)   # 🔥 너비 줄이고 싶으면 숫자 더 줄이면 됨

    # 헤더
    for j, h in enumerate(headers):
        t.rows[0].cells[j].text = str(h)

    # 데이터
    for i, r in enumerate(rows):
        for j in range(n_cols):
            val = r[j] if j < len(r) else ""
            t.rows[i+1].cells[j].text = str(val)
    # ✅ 자동폭 끄기 (핵심)
    t.autofit = False

    # 2단 셀 안에 들어갈 때 너무 넓으면 깨져서 보수적으로 폭 설정
    total_width = Inches(total_width_in)
    col_w = total_width / n_cols

    # 헤더
    for j in range(n_cols):
        h = headers[j] if j < len(headers) else ""
        cell = t.rows[0].cells[j]
        cell.width = col_w
        cell.text = str(h)

        for p in cell.paragraphs:
            if p.runs:
                p.runs[0].bold = True
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0

    # 바디
    for i, r in enumerate(rows):
        for j in range(n_cols):
            val = r[j] if j < len(r) else ""
            cell = t.rows[i + 1].cells[j]
            cell.width = col_w
            cell.text = str(val)

            for p in cell.paragraphs:
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0


def first_text(payload: Dict[str, Any], keys: Tuple[str, ...] | List[str]) -> Optional[str]:
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _try_add_image(container, payload: Dict[str, Any]):
    """
    Division 같은 문제에서 tree_base png 등 이미지 넣기.
    생성기마다 키가 달라서 후보 키 여러 개 지원.
    """
    img_path = (
        payload.get("_image_path")
        or payload.get("image_path")
        or payload.get("tree_img")
        or payload.get("figure_path")
        or payload.get("fig_path")
    )

    if not isinstance(img_path, str) or not img_path.strip():
        return

    ip = img_path.strip()

    # 상대경로면, 실행 위치 기준으로 깨질 수 있으니
    # payload가 절대경로를 안 넣었다면, 일단 그대로 시도하고 실패하면 메시지
    if os.path.exists(ip):
        try:
            container.add_paragraph("")  # spacing
            # 2단 셀에 들어가므로 폭은 적당히
            container.add_picture(ip, width=Inches(1.2))
            container.add_paragraph("")  # spacing
        except Exception:
            _add_par(container, f"(이미지 삽입 실패: {ip})")
    else:
        _add_par(container, f"(이미지 경로 없음: {ip})")


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

    # 2단 구현: 1행 2열 "outer table"
    idx = 0
    pnum = 1

    while idx < len(selected):
        if two_columns:
            outer = doc.add_table(rows=1, cols=2)
            outer.autofit = False
            outer.style = "Table Grid"  # 테두리 싫으면 주석 처리 가능

            # 2단 폭(환경마다 다르지만 대체로 안정적으로)
            outer.columns[0].width = Inches(3.4)
            outer.columns[1].width = Inches(3.4)

            left = outer.rows[0].cells[0]
            right = outer.rows[0].cells[1]

            targets = [(left, selected[idx], pnum)]
            idx += 1
            pnum += 1
            if idx < len(selected):
                targets.append((right, selected[idx], pnum))
                idx += 1
                pnum += 1
        else:
            targets = [(doc, selected[idx], pnum)]
            idx += 1
            pnum += 1

        for container, it, num in targets:
            payload = it.payload or {}
            _add_par(container, f"[문제 {num}]  ID: {it.pid}  ({it.prefix})", bold=True)

            # 본문/요구사항
            ptxt = first_text(payload, cfg.problem_text_keys)
            atxt = first_text(payload, cfg.ask_line_keys)

            if ptxt:
                _add_par(container, "문제", bold=True)
                _add_par(container, ptxt)
            if atxt:
                _add_par(container, "요구사항", bold=True)
                _add_par(container, atxt)

            # 이미지(있으면)
            _try_add_image(container, payload)

            # 제시표(가능하면 표로)
            given = try_find_table(payload, list(cfg.given_table_keys)) or payload.get("_given_table")
            if given is not None:
                _add_par(container, "제시표", bold=True)
                _add_grid_table(container, given, total_width_in=3.2)
                _add_par(container, "")

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

        _add_par(doc, "정답", bold=True)
        _add_par(doc, ans or "(없음)")

        if include_full_table:
            full = try_find_table(payload, list(cfg.full_table_keys)) or payload.get("_full_table")
            if full is not None:
                _add_par(doc, "완성표", bold=True)
                # 정답 파트는 2단이 아니라 본문 전체폭이라 조금 넓게
                _add_grid_table(doc, full, total_width_in=6.4)

        if include_explanations:
            _add_par(doc, "해설", bold=True)
            _add_par(doc, expl or "(없음)")

        _add_par(doc, "-" * 40)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
