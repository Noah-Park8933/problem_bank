# problem_bank_web.py
# ------------------------------------------------------------
# ✅ Streamlit 문제은행 뷰어 (PACK JSON 기반) - Arrow/pyarrow 안전버전
#
# 해결된 문제:
# - pyarrow.lib.ArrowInvalid: cannot mix list and non-list ...  (DataFrame 혼합 타입)
#   -> 모든 dataframe 출력은 safe_df()를 거쳐 문자열화 후 출력
#
# 기능:
# 1) PACK JSON 자동 탐색/통합(packs 폴더)
# 2) 문제 미리보기: 표/해설 자동 렌더링(모듈별 payload 자동 감지)
# 3) 선택 표시(✅) + 선택만 보기
# 4) ID prefix(모듈)별 필터 + ID 검색
# 5) 그룹 전체 선택/해제
# 6) 선택 문항 DOCX 내보내기
#
# 실행:
#   pip install streamlit pandas python-docx
#   streamlit run problem_bank_web.py --server.address 0.0.0.0 --server.port 8501
# ------------------------------------------------------------

import os
import re
import json
import time
import glob
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import streamlit as st
import pandas as pd

from docx import Document
from docx.shared import Pt


# =========================
# CONFIG
# =========================


# ------------------------------
# Table detection helpers (robust across modules)
# ------------------------------
PREFERRED_TABLE_KEYS = [
    "masked_table", "given_table", "table", "grid", "matrix",
    "full_table", "answer_table", "sums_mask", "sums", "data_table",
    "table_md", "masked_table_md",
]

def _looks_like_cell_labels(keys) -> bool:
    s = [str(k) for k in keys]
    if not s:
        return False
    if all(len(x) == 1 and x.isalpha() for x in s):  # A,B,C...
        return True
    if all(x in {"I","II","III","IV","V","VI","VII","VIII"} for x in s):
        return True
    if all(x in {"가","나","다","라","마","바","사","아","자","차"} for x in s):
        return True
    return False

def _looks_like_gene_labels(keys) -> bool:
    s = [str(k) for k in keys]
    if not s:
        return False
    # allele/gene symbols like A,a,B,b,D,d etc.
    if all(len(x) <= 2 and x.replace("/", "").isalpha() for x in s):
        return True
    if any(x in {"A","a","B","b","D","d","E","e","F","f","G","g","H","h"} for x in s):
        return True
    if any(x in {"응집원A","응집원B","ALPHA","BETA","α","β"} for x in s):
        return True
    return False

def is_table_like(obj) -> bool:
    if obj is None:
        return False
    if isinstance(obj, dict):
        # schema dict
        if {"rows","cols","data"}.issubset(obj.keys()) and isinstance(obj.get("data"), list):
            return True
        if {"index","columns","values"}.issubset(obj.keys()) and isinstance(obj.get("values"), list):
            return True
        vals = list(obj.values())
        if len(vals) >= 2 and all(isinstance(v, dict) for v in vals):
            return True
        if len(vals) >= 2 and all(isinstance(v, list) for v in vals):
            lens = [len(v) for v in vals]
            return min(lens) >= 2 and max(lens) == min(lens)
    if isinstance(obj, list) and len(obj) >= 2:
        if all(isinstance(r, dict) for r in obj):
            return True
        if all(isinstance(r, list) for r in obj):
            lens = [len(r) for r in obj]
            return min(lens) >= 2 and max(lens) == min(lens)
    return False

def deep_find_tables(payload, max_nodes: int = 6000):
    stack = [("", payload)]
    seen = 0
    while stack and seen < max_nodes:
        path, obj = stack.pop()
        seen += 1
        if is_table_like(obj):
            yield path, obj
        if isinstance(obj, dict):
            for k,v in obj.items():
                stack.append((f"{path}.{k}" if path else str(k), v))
        elif isinstance(obj, list):
            # cap deep lists
            for i,v in enumerate(obj[:200]):
                stack.append((f"{path}[{i}]", v))

def pick_tables(payload: dict):
    """
    Return list of (label, table_obj) candidates in preference order.
    """
    if not isinstance(payload, dict):
        return []
    out = []
    # 1) preferred keys first (direct)
    for k in PREFERRED_TABLE_KEYS:
        if k in payload and is_table_like(payload[k]):
            out.append((k, payload[k]))
    if out:
        return out

    # 2) nested preferred keys
    pref = set(PREFERRED_TABLE_KEYS)
    for path,obj in deep_find_tables(payload):
        tail = path.split(".")[-1] if path else ""
        if tail in pref:
            out.append((path, obj))
    if out:
        return out

    # 3) any table-like fallback
    for path,obj in deep_find_tables(payload):
        out.append((path or "table", obj))
        break
    return out
DEFAULT_PACK_DIR = "packs"
EXPORT_DIR = "exports"
APP_TITLE = "문제은행 (PACK JSON)"

DIFF_KEYS = ["difficulty", "diff", "level", "score", "difficulty_score"]

PACK_GLOBS = [
    "*_PACK_*.json",
    "*PACK*.json",
    "*.json",  # ✅ 최후 방어: packs 안의 json은 전부 후보로 본다(원하면 지워도 됨)
]


# =========================
# Data model
# =========================
@dataclass
class PackItem:
    id: str
    module: str
    qnum: Optional[int]
    id_prefix: str
    payload: Dict[str, Any]
    src_path: str


# =========================
# Arrow-safe helpers
# =========================
def to_cell(v: Any) -> str:
    """Streamlit/pyarrow 안전하게 표시하기 위해 무조건 문자열로 변환."""
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


def safe_df(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame 전체를 문자열로 변환하여 pyarrow 혼합 타입 에러 방지."""
    try:
        out = df.copy()
        for c in out.columns:
            out[c] = out[c].map(to_cell)
        # index도 문자열
        out.index = [to_cell(x) for x in out.index]
        return out
    except Exception:
        # 최악의 경우 통째로 문자열화
        return df.astype(str)


def safe_dataframe(df: pd.DataFrame, **kwargs):
    """st.dataframe 래퍼."""
    st.dataframe(safe_df(df), **kwargs)


# =========================
# IO / pack loading
# =========================
def safe_load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return None
    except Exception:
        return None


def discover_pack_files(pack_dir: str) -> List[str]:
    paths = []
    for pat in PACK_GLOBS:
        paths.extend(glob.glob(os.path.join(pack_dir, pat)))
    paths = sorted(list(dict.fromkeys(paths)))
    return paths


def extract_id_prefix(pid: str, module: str) -> str:
    m = re.match(r"^([A-Za-z0-9]+)_", pid)
    if m:
        return m.group(1)
    return module


def normalize_items_from_pack_json(data: Any, src_path: str) -> List[PackItem]:
    """
    PACK JSON을 최대한 방어적으로 파싱.
    표준: {"module": "...", "items":[{"id":..., "payload":...}, ...]}
    """
    out: List[PackItem] = []

    # case1) 표준 dict + items
    if isinstance(data, dict) and isinstance(data.get("items", None), list):
        module_default = str(data.get("module", "UNKNOWN"))
        for idx, it in enumerate(data["items"], start=1):
            if not isinstance(it, dict):
                continue
            pid = str(it.get("id") or it.get("problem_id") or "")
            if not pid:
                raw = json.dumps(it, ensure_ascii=False)
                pid = "NOID_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
            mod = str(it.get("module", module_default) or module_default)
            qnum = it.get("qnum", idx)
            payload = it.get("payload", {})
            if payload is None or not isinstance(payload, dict):
                payload = {"_raw": payload}
            id_prefix = extract_id_prefix(pid, mod)
            out.append(PackItem(pid, mod, qnum, id_prefix, payload, src_path))
        return out

    # case2) 리스트 자체가 문제 리스트
    if isinstance(data, list):
        for idx, it in enumerate(data, start=1):
            if not isinstance(it, dict):
                continue
            pid = str(it.get("id") or it.get("problem_id") or "")
            if not pid:
                raw = json.dumps(it, ensure_ascii=False)
                pid = "NOID_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
            mod = str(it.get("module", "UNKNOWN"))
            payload = it.get("payload", None)
            if payload is None:
                payload = {k: v for k, v in it.items() if k not in ["id", "module", "qnum", "seed"]}
            if not isinstance(payload, dict):
                payload = {"_raw": payload}
            id_prefix = extract_id_prefix(pid, mod)
            out.append(PackItem(pid, mod, it.get("qnum", idx), id_prefix, payload, src_path))
        return out

    # case3) 단일 문제 dict (가끔 그럴 수 있음)
    if isinstance(data, dict) and ("id" in data or "payload" in data):
        pid = str(data.get("id") or data.get("problem_id") or "")
        if not pid:
            raw = json.dumps(data, ensure_ascii=False)
            pid = "NOID_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
        mod = str(data.get("module", "UNKNOWN"))
        payload = data.get("payload", None)
        if payload is None:
            payload = {k: v for k, v in data.items() if k not in ["id", "module", "qnum", "seed"]}
        if not isinstance(payload, dict):
            payload = {"_raw": payload}
        id_prefix = extract_id_prefix(pid, mod)
        return [PackItem(pid, mod, data.get("qnum", 1), id_prefix, payload, src_path)]

    return out


def get_difficulty(payload: Dict[str, Any]) -> str:
    for k in DIFF_KEYS:
        if k in payload:
            return to_cell(payload.get(k))
    return "미지정"


def ensure_dirs():
    os.makedirs(DEFAULT_PACK_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)


@st.cache_data(show_spinner=False)
def load_all_items(pack_dir: str) -> List[PackItem]:
    paths = discover_pack_files(pack_dir)
    items: List[PackItem] = []
    for path in paths:
        data = safe_load_json(path)
        if data is None:
            continue
        items.extend(normalize_items_from_pack_json(data, path))

    # id 중복 제거(마지막 로드 우선)
    dedup: Dict[str, PackItem] = {}
    for it in items:
        dedup[it.id] = it
    return list(dedup.values())


# =========================
# Render helpers (Streamlit)
# =========================
def render_kv(payload: Dict[str, Any], keys: List[str], title: str):
    cols = []
    vals = []
    for k in keys:
        if k in payload:
            cols.append(k)
            vals.append(to_cell(payload.get(k)))
    if cols:
        st.markdown(f"**{title}**")
        df = pd.DataFrame({"key": cols, "value": vals})
        safe_dataframe(df, use_container_width=True)


def grid_to_df(grid: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    rows = list(grid.keys())
    cols: List[str] = []
    for r in rows:
        if isinstance(grid.get(r), dict):
            cols = list(dict.fromkeys(cols + list(grid[r].keys())))
    data = []
    for r in rows:
        row_dict = grid.get(r, {}) if isinstance(grid.get(r), dict) else {}
        data.append([row_dict.get(c, "") for c in cols])
    return pd.DataFrame(data, index=rows, columns=cols)


def rows_list_to_df(row_labels: List[str], col_labels: List[str], rows: Dict[str, List[Any]]) -> pd.DataFrame:
    data = []
    for r in row_labels:
        arr = rows.get(r, [])
        arr2 = []
        for j in range(len(col_labels)):
            v = arr[j] if j < len(arr) else ""
            if v is None:
                v = "?"
            arr2.append(v)
        data.append(arr2)
    return pd.DataFrame(data, index=row_labels, columns=col_labels)


def try_render_tables(payload: Dict[str, Any]):
    """
    payload에서 표로 보일 수 있는 것들을 자동 렌더링.
    """
    def render_table_dict(key: str, title: str):
        if key in payload and isinstance(payload[key], dict) and payload[key]:
            st.markdown(f"**{title}**")
            val = payload[key]
            # {row: [..]} 형태
            if isinstance(next(iter(val.values())), list):
                rows = list(val.keys())
                ncol = len(next(iter(val.values())))
                cols = [f"C{i+1}" for i in range(ncol)]
                df = rows_list_to_df(rows, cols, val)
                safe_dataframe(df, use_container_width=True)
            else:
                df = grid_to_df(val)
                safe_dataframe(df, use_container_width=True)

    # DNAI / gene_detecting류
    render_table_dict("masked_table", "제시표(가림 포함)")
    render_table_dict("full_table", "완성표(정답표)")

    # DNA integration no-figure류
    render_table_dict("sums_mask", "제시표(가림 포함)")
    render_table_dict("sums_full", "완성표(정답표)")

    # agglutination/blood_grouping류 (있으면)
    render_table_dict("masked", "제시표(가림 포함)")
    render_table_dict("full", "완성표(정답표)")


def try_render_explanations(payload: Dict[str, Any]):
    if "chromosome_info" in payload:
        st.markdown("**염색체 정보**")
        st.write(to_cell(payload["chromosome_info"]))

    if "clues" in payload and isinstance(payload["clues"], list):
        st.markdown("**결정적 단서(Clues)**")
        for x in payload["clues"]:
            st.write("- " + to_cell(x))

    if "explanation" in payload:
        st.markdown("**해설**")
        exp = payload["explanation"]
        if isinstance(exp, list):
            for line in exp:
                st.write("- " + to_cell(line))
        else:
            st.write(to_cell(exp))

    if "reasons" in payload and isinstance(payload["reasons"], dict):
        st.markdown("**근거(Reasons)**")
        st.json(payload["reasons"], expanded=False)


def payload_debug(payload: Dict[str, Any]):
    st.caption("payload 키 목록(디버그)")
    st.code(", ".join(sorted(list(payload.keys()))))


# =========================
# DOCX export
# =========================
def set_doc_style(doc: Document, font_name="바탕", font_size_pt=9):
    style = doc.styles["Normal"]
    style.font.name = font_name
    style.font.size = Pt(font_size_pt)


def add_docx_table_from_df(doc: Document, df: pd.DataFrame, title: Optional[str] = None):
    if title:
        p = doc.add_paragraph(title)
        if p.runs:
            p.runs[0].bold = True

    df2 = safe_df(df)
    nrows, ncols = df2.shape
    table = doc.add_table(rows=nrows + 1, cols=ncols + 1)
    table.style = "Table Grid"

    table.cell(0, 0).text = ""
    for j, c in enumerate(df2.columns):
        table.cell(0, j + 1).text = str(c)

    for i, r in enumerate(df2.index):
        table.cell(i + 1, 0).text = str(r)
        for j, c in enumerate(df2.columns):
            table.cell(i + 1, j + 1).text = str(df2.loc[r, c])


def export_docx(selected: List[PackItem]) -> str:
    ensure_dirs()
    out_name = os.path.join(EXPORT_DIR, f"Selected_{int(time.time())}.docx")
    doc = Document()
    set_doc_style(doc, font_name="바탕", font_size_pt=9)

    doc.add_paragraph("[선택 문항 출력]").runs[0].bold = True
    doc.add_paragraph(f"총 {len(selected)}문항")
    doc.add_paragraph("")

    for idx, p in enumerate(selected, start=1):
        head = doc.add_paragraph(f"[{idx}] ID: {p.id}   (모듈: {p.module})")
        if head.runs:
            head.runs[0].bold = True

        payload = p.payload

        # 테이블 후보 출력
        def add_any_table(key: str, title: str):
            if key in payload and isinstance(payload[key], dict) and payload[key]:
                val = payload[key]
                if isinstance(next(iter(val.values())), list):
                    rows = list(val.keys())
                    ncol = len(next(iter(val.values())))
                    cols = [f"C{i+1}" for i in range(ncol)]
                    df = rows_list_to_df(rows, cols, val)
                else:
                    df = grid_to_df(val)
                add_docx_table_from_df(doc, df, title=title)
                doc.add_paragraph("")

        add_any_table("masked_table", "제시표(가림 포함)")
        add_any_table("full_table", "완성표(정답표)")
        add_any_table("sums_mask", "제시표(가림 포함)")
        add_any_table("sums_full", "완성표(정답표)")
        add_any_table("masked", "제시표(가림 포함)")
        add_any_table("full", "완성표(정답표)")

        # 해설 후보
        if "chromosome_info" in payload:
            doc.add_paragraph("[염색체 정보]").runs[0].bold = True
            doc.add_paragraph(to_cell(payload["chromosome_info"]))
            doc.add_paragraph("")

        if "clues" in payload and isinstance(payload["clues"], list):
            doc.add_paragraph("[결정적 단서]").runs[0].bold = True
            for x in payload["clues"]:
                doc.add_paragraph("- " + to_cell(x))
            doc.add_paragraph("")

        if "explanation" in payload:
            doc.add_paragraph("[해설]").runs[0].bold = True
            exp = payload["explanation"]
            if isinstance(exp, list):
                for line in exp:
                    doc.add_paragraph("- " + to_cell(line))
            else:
                doc.add_paragraph(to_cell(exp))
            doc.add_paragraph("")

        # 디버그용 payload 키
        doc.add_paragraph("[payload 키]").runs[0].bold = True
        doc.add_paragraph(", ".join(sorted(list(payload.keys()))))
        doc.add_paragraph("")
        doc.add_paragraph("-" * 40)

    doc.save(out_name)
    return out_name


# =========================
# App
# =========================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    ensure_dirs()

    st.sidebar.header("설정")
    pack_dir = st.sidebar.text_input("PACK 폴더", value=DEFAULT_PACK_DIR).strip()
    if not os.path.isdir(pack_dir):
        st.sidebar.warning("PACK 폴더가 없어서 새로 만들었음")
        os.makedirs(pack_dir, exist_ok=True)

    # DEBUG (원하면 지워도 됨)
    with st.sidebar.expander("DEBUG", expanded=False):
        st.write("cwd =", os.getcwd())
        st.write("pack_dir =", pack_dir)
        st.write("exists =", os.path.isdir(pack_dir))
        st.write("json count =", len(glob.glob(os.path.join(pack_dir, "*.json"))))

    items = load_all_items(pack_dir)
    st.sidebar.caption(f"로드된 문항: {len(items)}개")

    # Session state
    if "selected_ids" not in st.session_state:
        st.session_state["selected_ids"] = set()
    if "show_selected_only" not in st.session_state:
        st.session_state["show_selected_only"] = False

    # Filters
    modules = sorted(list(set([it.id_prefix for it in items])))
    module_sel = st.sidebar.multiselect("모듈(ID prefix) 필터", options=modules, default=modules)

    search_id = st.sidebar.text_input("ID 검색(부분일치)", value="").strip()

    st.sidebar.divider()
    colA, colB = st.sidebar.columns(2)
    with colA:
        if st.button("✅ 선택만 보기"):
            st.session_state["show_selected_only"] = True
    with colB:
        if st.button("📌 전체 보기"):
            st.session_state["show_selected_only"] = False

    # Group select / deselect
    st.sidebar.divider()
    st.sidebar.subheader("그룹 선택/해제")

    if st.sidebar.button("현재 필터 그룹 전체 선택"):
        for it in items:
            if it.id_prefix in module_sel and (search_id.lower() in it.id.lower() if search_id else True):
                st.session_state["selected_ids"].add(it.id)

    if st.sidebar.button("현재 필터 그룹 전체 해제"):
        remove_ids = []
        for pid in list(st.session_state["selected_ids"]):
            it = next((x for x in items if x.id == pid), None)
            if it and it.id_prefix in module_sel and (search_id.lower() in it.id.lower() if search_id else True):
                remove_ids.append(pid)
        for pid in remove_ids:
            st.session_state["selected_ids"].discard(pid)

    if st.sidebar.button("선택 전체 해제(전부)"):
        st.session_state["selected_ids"] = set()

    # Export
    st.sidebar.divider()
    st.sidebar.subheader("내보내기")
    if st.sidebar.button("선택 문항 DOCX 내보내기"):
        selected = [it for it in items if it.id in st.session_state["selected_ids"]]
        if not selected:
            st.sidebar.warning("선택된 문항이 없음")
        else:
            path = export_docx(selected)
            st.sidebar.success("DOCX 생성 완료")
            st.sidebar.write(path)

    # Apply filters
    filtered = []
    for it in items:
        if it.id_prefix not in module_sel:
            continue
        if search_id and search_id.lower() not in it.id.lower():
            continue
        if st.session_state["show_selected_only"] and it.id not in st.session_state["selected_ids"]:
            continue
        filtered.append(it)

    filtered.sort(key=lambda x: (x.id_prefix, x.qnum if x.qnum is not None else 10**9, x.id))
    st.caption(f"표시 중: {len(filtered)}개 / 전체 {len(items)}개")

    for it in filtered:
        selected = (it.id in st.session_state["selected_ids"])
        badge = "✅" if selected else "⬜"
        with st.expander(f"{badge} {it.id}   ({it.id_prefix})   | src={os.path.basename(it.src_path)}", expanded=False):
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                if st.button("선택/해제", key=f"tog_{it.id}"):
                    if it.id in st.session_state["selected_ids"]:
                        st.session_state["selected_ids"].discard(it.id)
                    else:
                        st.session_state["selected_ids"].add(it.id)
                    st.rerun()

            with c2:
                st.write(f"- module: `{it.module}`")
                st.write(f"- qnum: `{it.qnum}`")
                st.write(f"- 난이도: `{get_difficulty(it.payload)}`")

            with c3:
                render_kv(it.payload, ["x_loci", "sum_col", "ineq", "map_row_to_fig", "mask_used"], "요약")

            st.divider()
            try_render_tables(it.payload)

            st.divider()
            try_render_explanations(it.payload)

            st.divider()
            payload_debug(it.payload)

    st.sidebar.caption(f"선택됨: {len(st.session_state['selected_ids'])}개")


if __name__ == "__main__":
    main()
