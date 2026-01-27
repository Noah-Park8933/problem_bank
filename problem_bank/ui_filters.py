import streamlit as st
from typing import List, Tuple
from .loader import ProblemItem
from .config import AppConfig

def filter_items(cfg: AppConfig, items: List[ProblemItem]) -> Tuple[List[ProblemItem], dict]:
    # 사이드 필터 UI
    prefixes = sorted(set(it.prefix for it in items))
    modules = sorted(set(it.module for it in items))

    st.sidebar.subheader("필터")
    prefix_sel = st.sidebar.multiselect("ID Prefix", prefixes, default=prefixes)
    module_sel = st.sidebar.multiselect("Module", modules, default=modules)
    q = st.sidebar.text_input("검색(본문/ID)", "")

    filtered = []
    ql = q.strip().lower()
    for it in items:
        if it.prefix not in prefix_sel:
            continue
        if it.module not in module_sel:
            continue
        if ql:
            if ql not in it.pid.lower() and ql not in str(it.payload).lower():
                continue
        filtered.append(it)

    meta = {"prefix_sel": prefix_sel, "module_sel": module_sel, "q": q}
    return filtered, meta