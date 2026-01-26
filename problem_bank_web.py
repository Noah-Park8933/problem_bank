# problem_bank_web.py
# ------------------------------------------------------------
# Streamlit PACK(JSON) 문제은행 (통합 안정판)
#
# 포함 기능
# 1) PACK 폴더 자동 스캔(재귀) + JSON 자동 로드(다양한 포맷 호환)
# 2) Pagination + 미리보기(우측) + 선택 표시/선택만 보기
# 3) ID prefix(모듈)별 그룹 접기/펼치기
# 4) 그룹 전체 선택/해제: (a) 현재 필터 전체, (b) 현재 화면(페이지) 전체, (c) prefix 그룹 단위
# 5) 난이도(difficulty) 필터 UI
# 6) DOCX 내보내기: 문제는 2단(페이지당 2문항), 정답/해설은 뒤에 모아서
# 7) pyarrow 혼합 타입 에러 방지(표/요약 모두 문자열화)
#
# 실행:
#   pip install streamlit python-docx pandas
#   streamlit run problem_bank_web.py
# ------------------------------------------------------------

import os
import re
import json
import math
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from io import BytesIO 
import streamlit as st
from pathlib import Path
import os
import glob

# ✅ PACK 경로 우선순위:
#  1) GitHub 배포용: ./packs
#  2) 로컬 생성용:  ./output (또는 ./output/packs, ./output/pack 등도 자동 탐색)
APP_DIR = Path(__file__).resolve().parent

DEFAULT_PACK_DIRS = [
    APP_DIR / "packs",
    APP_DIR / "output",
    APP_DIR / "output" / "packs",
    APP_DIR / "output" / "pack",
]

def find_pack_json_files(base_dirs=None):
    """여러 후보 폴더에서 *.pack.json / *.json을 폭넓게 탐색."""
    base_dirs = base_dirs or DEFAULT_PACK_DIRS
    files = []
    for d in base_dirs:
        if not d.exists():
            continue
        # pack 확장 우선
        files += list(d.glob("*.pack.json"))
        # 혹시 pack.json이 아닌 이름으로 저장된 경우도 대비(원하면 주석 처리 가능)
        files += [p for p in d.glob("*.json") if p.name.endswith(".pack.json") or "pack" in p.name.lower()]
    # 중복 제거 + 정렬
    uniq = sorted({str(p) for p in files})
    return uniq

try:
    import pandas as pd
except Exception:
    pd = None


# =========================
# CONFIG
# =========================
APP_TITLE = "문제은행 (PACK JSON)"
DEFAULT_PACK_DIR = os.path.join(os.path.dirname(__file__), "packs")  # 네 폴더에 맞게 수정
EXPORT_DIR_DEFAULT = os.path.join(os.path.dirname(__file__), "exports")

PAGE_SIZES = [50, 100, 150, 200, 300]
DEFAULT_PAGE_SIZE = 100

# PACK/Item 텍스트 키 후보들(모듈마다 달라서 넓게)
PROBLEM_TEXT_KEYS = [
    "problem_text_md", "problem_md", "stem_md", "stem",
    "problem_text", "prompt_md", "prompt", "problem", "question_md",
    "question", "description_md", "description"
]
ASK_TEXT_KEYS = [
    "ask_line_md", "ask_md", "ask_line", "ask", "request_md",
    "request", "what_to_find_md", "what_to_find", "query_md",
    "query", "task_md", "task"
]
ANSWER_KEYS = [
    "answer_md", "answer", "ans", "correct", "key", "final_answer"
]
EXPLAIN_KEYS = [
    "explanation_md", "explain_md", "explanation", "explain",
    "solution_md", "solution", "reasons_md", "reasons", "rationale_md", "rationale"
]

# 표 데이터 후보 (dict or markdown table string)
GIVEN_TABLE_KEYS = [
    "table_md", "masked_table_md", "table", "masked", "masked_table",
    "given_table", "table_masked", "shown_table", "shown_table_md",
    "sums_mask", "sums_mask_md"
]
FULL_TABLE_KEYS = [
    "full_table_md", "full", "full_table", "answer_table", "table_full",
    "solved_table", "solved_table_md", "sums_full", "sums_full_md"
]

# 난이도 키 후보
DIFF_KEYS = ["difficulty", "diff", "level", "score", "difficulty_score"]


# =========================
# Data model
# =========================
@dataclass
class ProblemItem:
    id: str
    prefix: str  # id_prefix or module_code
    module_code: Optional[str]
    qnum: Optional[int]
    payload: Dict[str, Any]
    src_path: str


# =========================
# Safe helpers (pyarrow/pandas)
# =========================
def to_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list, tuple, set)):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    try:
        return str(v)
    except Exception:
        return repr(v)


def safe_df(df: "pd.DataFrame") -> "pd.DataFrame":
    # pandas 있을 때만
    out = df.copy()
    for c in out.columns:
        out[c] = out[c].map(to_cell)
    out.index = [to_cell(x) for x in out.index]
    return out


def safe_dataframe(df: "pd.DataFrame", **kwargs):
    if pd is None:
        st.code(df.to_string())
        return
    st.dataframe(safe_df(df), **kwargs)


def safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    try:
        return json.dumps(x, ensure_ascii=False, indent=2)
    except Exception:
        return str(x)


def find_first(payload: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for k in keys:
        if k in payload and payload[k] not in (None, "", []):
            return payload[k]
    return None


def get_difficulty(payload: Dict[str, Any]) -> Optional[str]:
    for k in DIFF_KEYS:
        if k in payload and payload[k] not in (None, ""):
            return to_cell(payload[k])
    return None


def parse_qnum_from_id(pid: str) -> Optional[int]:
    # 예: "...-Q12" "..._12" "... 12" 등
    m = re.search(r"(?:^|[^0-9])([0-9]{1,4})(?:$|[^0-9])", pid)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


# =========================
# File discovery & load
# =========================
def discover_json_files(pack_dir: str) -> List[str]:
    out = []
    for root, _, files in os.walk(pack_dir):
        for fn in files:
            if fn.lower().endswith(".json"):
                out.append(os.path.join(root, fn))
    out.sort()
    return out


def dir_signature(paths: List[str]) -> str:
    # 파일 개수/mtime 기반 간단 시그니처(새로 생성한 json 반영)
    parts = []
    for p in paths:
        try:
            stt = os.stat(p)
            parts.append(f"{os.path.basename(p)}:{int(stt.st_mtime)}:{stt.st_size}")
        except Exception:
            parts.append(f"{os.path.basename(p)}:ERR")
    return str(hash("|".join(parts)))


def normalize_item(obj: Dict[str, Any], src_path: str, outer_defaults: Dict[str, Any]) -> Optional[ProblemItem]:
    # outer_defaults: pack level module_code/id_prefix 같은 거
    pid = obj.get("id") or obj.get("problem_id") or obj.get("uuid")
    if not pid:
        return None

    module_code = obj.get("module_code") or obj.get("module") or outer_defaults.get("module_code")
    id_prefix = obj.get("id_prefix") or outer_defaults.get("id_prefix") or module_code or "UNKNOWN"
    prefix = id_prefix

    payload = {}
    # payload가 있으면 우선
    if isinstance(obj.get("payload"), dict):
        payload.update(obj["payload"])
    # 그리고 item 레벨 텍스트도 payload로 병합(웹에서 찾기 쉽게)
    for k in (["problem_text_md", "ask_line_md", "answer_md", "explanation_md", "table_md"] +
              PROBLEM_TEXT_KEYS + ASK_TEXT_KEYS + ANSWER_KEYS + EXPLAIN_KEYS + GIVEN_TABLE_KEYS + FULL_TABLE_KEYS):
        if k in obj and k not in ("payload",):
            payload.setdefault(k, obj.get(k))
    # outer에서 내려온 것도 보조로
    for k in ("module_code", "id_prefix"):
        payload.setdefault(k, outer_defaults.get(k))

    qnum = obj.get("qnum")
    if qnum is None:
        qnum = parse_qnum_from_id(pid)

    return ProblemItem(
        id=str(pid),
        prefix=str(prefix),
        module_code=str(module_code) if module_code else None,
        qnum=qnum if isinstance(qnum, int) else None,
        payload=payload,
        src_path=src_path,
    )


@st.cache_data(show_spinner=False)
def load_all_items_cached(pack_dir: str, sig: str) -> Tuple[List[ProblemItem], List[Tuple[str, str]]]:
    items: List[ProblemItem] = []
    bad: List[Tuple[str, str]] = []

    paths = discover_json_files(pack_dir)
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            bad.append((path, f"{type(e).__name__}: {e}"))
            continue

        # Case A: pack format {module_code,id_prefix,items:[...]}
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            outer_defaults = {
                "module_code": data.get("module_code") or data.get("module"),
                "id_prefix": data.get("id_prefix") or data.get("module_code") or data.get("module"),
            }
            for obj in data["items"]:
                if isinstance(obj, dict):
                    it = normalize_item(obj, path, outer_defaults)
                    if it:
                        items.append(it)
            continue

        # Case B: single item dict
        if isinstance(data, dict):
            outer_defaults = {"module_code": data.get("module_code") or data.get("module"),
                              "id_prefix": data.get("id_prefix") or data.get("module_code") or data.get("module")}
            it = normalize_item(data, path, outer_defaults)
            if it:
                items.append(it)
            else:
                # payload만 있는 경우도 있으니 fallback: id가 outer에 있을 수도
                bad.append((path, "No valid item id in this json"))
            continue

        bad.append((path, "Unsupported json format"))
    # id 중복은 마지막 로드 우선
    dedup: Dict[str, ProblemItem] = {}
    for it in items:
        dedup[it.id] = it
    return list(dedup.values()), bad


def get_fields(payload: Dict[str, Any]) -> Tuple[str, str, str, str]:
    ptxt = find_first(payload, PROBLEM_TEXT_KEYS)
    atxt = find_first(payload, ASK_TEXT_KEYS)
    ans = find_first(payload, ANSWER_KEYS)
    expl = find_first(payload, EXPLAIN_KEYS)
    return safe_str(ptxt), safe_str(atxt), safe_str(ans), safe_str(expl)


# =========================
# Table rendering
# =========================
def dict_table_to_df(tbl: Any) -> Optional["pd.DataFrame"]:
    if pd is None:
        return None
    if not isinstance(tbl, dict) or not tbl:
        return None

    # 형태 1: {row:{col:val}}
    first_v = next(iter(tbl.values()))
    if isinstance(first_v, dict):
        rows = list(tbl.keys())
        cols: List[str] = []
        for r in rows:
            if isinstance(tbl.get(r), dict):
                cols = list(dict.fromkeys(cols + list(tbl[r].keys())))
        data = []
        for r in rows:
            rowd = tbl.get(r, {}) if isinstance(tbl.get(r), dict) else {}
            data.append([rowd.get(c, "") for c in cols])
        return pd.DataFrame(data, index=rows, columns=cols)

    # 형태 2: {row:[...]}
    if isinstance(first_v, list):
        rows = list(tbl.keys())
        ncol = len(first_v)
        cols = [f"C{i+1}" for i in range(ncol)]
        data = []
        for r in rows:
            arr = tbl.get(r, [])
            arr2 = []
            for j in range(ncol):
                v = arr[j] if j < len(arr) else ""
                arr2.append(v)
            data.append(arr2)
        return pd.DataFrame(data, index=rows, columns=cols)

    return None


def render_table_any(payload: Dict[str, Any], which: str):
    # which="given" or "full"
    keys = GIVEN_TABLE_KEYS if which == "given" else FULL_TABLE_KEYS
    tbl = find_first(payload, keys)
    if tbl is None:
        st.info("표 데이터가 없습니다.")
        return

    # markdown table이면 그냥 출력
    if isinstance(tbl, str) and ("|" in tbl) and ("---" in tbl):
        st.markdown(tbl)
        return

    # dict면 dataframe로
    df = dict_table_to_df(tbl)
    if df is not None:
        safe_dataframe(df, use_container_width=True)
        return

    # 그 외는 json text
    st.code(safe_str(tbl))


def render_summary(payload: Dict[str, Any]):
    # payload에서 대표 키 몇 개만 뽑아 보여주기(혼합 타입 방지)
    show_keys = []
    for k in ["col_map", "row_map", "mask_used", "ineq", "sum_col", "x_loci", "x_locus", "x_pair", "answer_num", "ox"]:
        if k in payload:
            show_keys.append(k)
    if not show_keys:
        return
    st.markdown("#### 요약")
    data = {"key": [], "value": []}
    for k in show_keys:
        data["key"].append(k)
        data["value"].append(to_cell(payload.get(k)))
    if pd is not None:
        safe_dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.code("\n".join([f"{k}: {payload.get(k)}" for k in show_keys]))


# =========================
# DOCX export (2 columns + answers at end)
# =========================
def ensure_export_dir(out_dir: str):
    os.makedirs(out_dir, exist_ok=True)


def add_doc_paragraph(cell_or_doc, text: str, bold: bool = False):
    if not text:
        return
    p = cell_or_doc.add_paragraph(text)
    if p.runs:
        p.runs[0].bold = bold


def add_doc_block(cell_or_doc, title: str, content: str):
    if not content:
        return
    add_doc_paragraph(cell_or_doc, title, bold=True)
    for line in content.splitlines():
        cell_or_doc.add_paragraph(line)


def export_docx(selected: List[ProblemItem], include_explanations: bool, include_full_table: bool) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "바탕"
    style.font.size = Pt(9)

    # 문제 파트: 2단(페이지당 2문항)
    idx = 0
    pnum = 1
    while idx < len(selected):
        tbl = doc.add_table(rows=1, cols=2)
        left = tbl.rows[0].cells[0]
        right = tbl.rows[0].cells[1]

        def fill(cell, it: ProblemItem, num: int):
            ptxt, atxt, ans, expl = get_fields(it.payload)

            add_doc_paragraph(cell, f"[문제 {num}]  ID: {it.id}  ({it.prefix})", bold=True)
            if ptxt:
                add_doc_block(cell, "문제", ptxt)
            if atxt:
                add_doc_block(cell, "요구사항", atxt)

            # 제시표
            add_doc_paragraph(cell, "제시표", bold=True)
            # 표를 markdown/text로 넣기 위해 streamlit 렌더링 대신 문자열화
            tbl_obj = find_first(it.payload, GIVEN_TABLE_KEYS)
            if tbl_obj is None:
                cell.add_paragraph("(표 없음)")
            else:
                cell.add_paragraph(safe_str(tbl_obj))

            cell.add_paragraph("")  # spacing

        fill(left, selected[idx], pnum)
        idx += 1
        pnum += 1

        if idx < len(selected):
            fill(right, selected[idx], pnum)
            idx += 1
            pnum += 1

        if idx < len(selected):
            doc.add_page_break()

    # 정답/해설 파트(뒤에 모아서)
    doc.add_page_break()
    add_doc_paragraph(doc, "[정답/해설]", bold=True)

    for i, it in enumerate(selected, start=1):
        ptxt, atxt, ans, expl = get_fields(it.payload)

        add_doc_paragraph(doc, f"{i}. ID: {it.id}  ({it.prefix})", bold=True)
        add_doc_block(doc, "정답", ans if ans else "(없음)")

        if include_full_table:
            full_obj = find_first(it.payload, FULL_TABLE_KEYS)
            if full_obj is not None:
                add_doc_block(doc, "완성표", safe_str(full_obj))

        if include_explanations:
            add_doc_block(doc, "해설", expl if expl else "(없음)")

        doc.add_paragraph("-" * 40)

    out_path = os.path.join(out_dir, f"export_{int(time.time())}.docx")
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()

# =========================
# App
# =========================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    # Session state
    if "selected_ids" not in st.session_state:
        st.session_state["selected_ids"] = set()
    if "page" not in st.session_state:
        st.session_state["page"] = 1
    if "preview_id" not in st.session_state:
        st.session_state["preview_id"] = None

    # Sidebar: settings
    st.sidebar.header("설정")
    pack_dir = st.sidebar.text_input("PACK 폴더", value=DEFAULT_PACK_DIR).strip()
    out_dir = st.sidebar.text_input("내보내기 폴더", value=EXPORT_DIR_DEFAULT).strip()

    if st.sidebar.button("🔄 새로고침(캐시 초기화)"):
        st.cache_data.clear()
        st.rerun()

    if not os.path.isdir(pack_dir):
        st.sidebar.warning("PACK 폴더가 없어서 새로 만들었습니다.")
        os.makedirs(pack_dir, exist_ok=True)

    paths = discover_json_files(pack_dir)
    sig = dir_signature(paths)
    items, bad_files = load_all_items_cached(pack_dir, sig)

    st.sidebar.caption(f"JSON {len(paths)}개 / 로드 {len(items)}문항")
    with st.sidebar.expander("❗읽기 실패한 JSON", expanded=False):
        st.write(f"{len(bad_files)}개")
        for p, err in bad_files[:300]:
            st.write(f"- {os.path.basename(p)}: {err}")

    # Sidebar: filters
    st.sidebar.header("필터")
    all_prefixes = sorted({it.prefix for it in items})
    sel_prefixes = st.sidebar.multiselect("ID prefix(모듈)", options=all_prefixes, default=all_prefixes)
    id_query = st.sidebar.text_input("ID 검색(부분일치)", value="").strip()
    only_selected = st.sidebar.checkbox("선택한 것만 보기", value=False)

    # Difficulty filter
    st.sidebar.subheader("난이도")
    diff_values = sorted({get_difficulty(it.payload) for it in items if get_difficulty(it.payload)})
    # "없음"도 옵션으로 넣기
    diff_values2 = ["(없음)"] + diff_values
    sel_diffs = st.sidebar.multiselect("난이도 값", options=diff_values2, default=diff_values2)

    # Apply filter
    filtered: List[ProblemItem] = []
    for it in items:
        if it.prefix not in sel_prefixes:
            continue
        if id_query and id_query.lower() not in it.id.lower():
            continue
        if only_selected and it.id not in st.session_state["selected_ids"]:
            continue
        d = get_difficulty(it.payload)
        d_norm = d if d else "(없음)"
        if d_norm not in sel_diffs:
            continue
        filtered.append(it)

    filtered.sort(key=lambda x: (x.prefix, x.qnum if x.qnum is not None else 10**9, x.id))

    # Pagination
    st.sidebar.header("페이지")
    page_size = st.sidebar.selectbox("페이지 크기", options=PAGE_SIZES, index=PAGE_SIZES.index(DEFAULT_PAGE_SIZE))
    max_pages = max(1, math.ceil(len(filtered) / page_size)) if filtered else 1

    colp1, colp2, colp3 = st.sidebar.columns([1, 1, 2])
    if colp1.button("⬅"):
        st.session_state["page"] = max(1, st.session_state["page"] - 1)
    if colp2.button("➡"):
        st.session_state["page"] = min(max_pages, st.session_state["page"] + 1)
    st.session_state["page"] = colp3.number_input("페이지", min_value=1, max_value=max_pages, value=int(st.session_state["page"]))

    start = (st.session_state["page"] - 1) * page_size
    end = min(len(filtered), start + page_size)
    view = filtered[start:end]

    st.caption(f"전체 {len(items)}문항 / 필터 {len(filtered)}문항 — 표시 {start+1 if filtered else 0}~{end}")

    # Top group actions (현재 필터 / 현재 화면)
    cga1, cga2, cga3, cga4 = st.columns([1, 1, 1, 2])
    if cga1.button("현재 필터 전체 선택"):
        for it in filtered:
            st.session_state["selected_ids"].add(it.id)
        st.rerun()
    if cga2.button("현재 필터 전체 해제"):
        for it in filtered:
            st.session_state["selected_ids"].discard(it.id)
        st.rerun()
    if cga3.button("현재 화면 전체 선택"):
        for it in view:
            st.session_state["selected_ids"].add(it.id)
        st.rerun()
    cga4.markdown(f"**선택됨:** {len(st.session_state['selected_ids'])}개")

    # Main layout: list + preview
    left, right = st.columns([1, 1])

    # LEFT: grouped list
    with left:
        st.subheader("문항 목록(그룹)")
        if not view:
            st.info("표시할 문항이 없습니다.")
        else:
            # 현재 화면(view)을 prefix별로 그룹
            by_prefix: Dict[str, List[ProblemItem]] = {}
            for it in view:
                by_prefix.setdefault(it.prefix, []).append(it)

            for pref in sorted(by_prefix.keys()):
                group = by_prefix[pref]
                sel_cnt = sum(1 for x in group if x.id in st.session_state["selected_ids"])
                with st.expander(f"[{pref}]  {sel_cnt}/{len(group)} 선택됨", expanded=False):
                    gb1, gb2, gb3 = st.columns([1, 1, 2])
                    if gb1.button("이 그룹(현재화면) 전체 선택", key=f"grp_sel_{pref}"):
                        for x in group:
                            st.session_state["selected_ids"].add(x.id)
                        st.rerun()
                    if gb2.button("이 그룹(현재화면) 전체 해제", key=f"grp_clr_{pref}"):
                        for x in group:
                            st.session_state["selected_ids"].discard(x.id)
                        st.rerun()
                    gb3.write("")

                    for it in group:
                        checked = it.id in st.session_state["selected_ids"]
                        row = st.columns([0.12, 0.63, 0.25])
                        with row[0]:
                            new_val = st.checkbox("", value=checked, key=f"sel_{it.id}")
                            if new_val and not checked:
                                st.session_state["selected_ids"].add(it.id)
                            if (not new_val) and checked:
                                st.session_state["selected_ids"].discard(it.id)
                        with row[1]:
                            d = get_difficulty(it.payload)
                            dshow = d if d else "-"
                            st.write(f"{it.id}  (난이도:{dshow})")
                        with row[2]:
                            if st.button("미리보기", key=f"pv_{it.id}"):
                                st.session_state["preview_id"] = it.id
                                st.rerun()

    # RIGHT: preview
    with right:
        st.subheader("미리보기")

        pid = st.session_state.get("preview_id")
        preview = None
        if pid:
            preview = next((x for x in items if x.id == pid), None)
        if preview is None and view:
            preview = view[0]

        if preview is None:
            st.info("표시할 문항이 없습니다.")
        else:
            try:
                ptxt, atxt, ans, expl = get_fields(preview.payload)
                st.markdown(f"**ID:** `{preview.id}`  \\\\  **모듈:** `{preview.prefix}`")

                if not ptxt and not atxt:
                    st.warning("문제 본문/요구사항 텍스트가 PACK에 없거나, 웹이 모르는 키로 저장되어 있습니다. "
                               "(생성기에서 problem_text_md, ask_line_md 저장 추천)")
                if ptxt:
                    st.markdown("#### 문제")
                    st.markdown(ptxt)
                if atxt:
                    st.markdown("#### 요구사항")
                    st.markdown(atxt)

                st.markdown("#### 제시표")
                render_table_any(preview.payload, which="given")

                with st.expander("완성표", expanded=False):
                    render_table_any(preview.payload, which="full")

                with st.expander("정답/해설", expanded=False):
                    st.markdown(f"**정답:** {ans if ans else '(없음)'}")
                    st.markdown("**해설:**")
                    st.markdown(expl if expl else "(없음)")

                with st.expander("요약/키", expanded=False):
                    render_summary(preview.payload)

                with st.expander("payload debug", expanded=False):
                    st.json(preview.payload)

            except Exception as e:
                st.error(f"미리보기 렌더링 실패: {type(e).__name__}: {e}")
                st.code(traceback.format_exc())
                st.json(preview.payload)

    # Export
    st.divider()
    st.subheader("내보내기")

    ex1, ex2, ex3, ex4 = st.columns([1, 1, 1, 2])
    include_expl = ex1.checkbox("해설 포함", value=True)
    include_full = ex2.checkbox("완성표 포함", value=False)

    if ex3.button("선택 전체 해제(전부)"):
        st.session_state["selected_ids"] = set()
        st.rerun()

    selected_items = [it for it in items if it.id in st.session_state["selected_ids"]]

    docx_bytes = None
    if ex4.button("📄 DOCX 생성(다운로드 준비)"):
        if not selected_items:
            st.warning("선택된 문항이 없습니다.")
    else:
        docx_bytes = export_docx(
            selected_items,
            include_explanations=include_expl,
            include_full_table=include_full,
        )
        st.success("DOCX 준비 완료! 아래 버튼으로 다운로드하세요.")

    if docx_bytes:
        st.download_button(
            label="⬇️ DOCX 다운로드",
            data=docx_bytes,
            file_name="selected_export.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    main()
