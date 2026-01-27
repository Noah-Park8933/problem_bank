import streamlit as st
from typing import List
from .loader import ProblemItem
from .config import AppConfig
from .state_manager import AppState
from .table_renderer import try_find_table, normalize_table_to_grid

def render_table_pretty(table_obj):
    headers, rows = normalize_table_to_grid(table_obj)
    # Streamlit 표
    import pandas as pd
    if rows and headers:
        df = pd.DataFrame([r[1:] for r in rows], index=[r[0] for r in rows], columns=headers[1:] if headers[0]=="" else headers)
        st.dataframe(df, use_container_width=True)

def render_list(cfg: AppConfig, state: AppState, items: List[ProblemItem], page: int):
    start = page * cfg.page_size
    end = min(len(items), start + cfg.page_size)
    page_items = items[start:end]

    for idx, it in enumerate(page_items):
        uid = it.uid
        checked = uid in state.selected_uids

        cols = st.columns([0.08, 0.62, 0.3])
        with cols[0]:
            new_checked = st.checkbox(" ", value=checked, key=f"chk_{uid}_{page}_{idx}")
            if new_checked:
                state.selected_uids.add(uid)
            else:
                state.selected_uids.discard(uid)

        with cols[1]:
            st.markdown(f"**{it.pid}**  `({it.prefix})`")
            # 본문/요구사항
            ptxt = _first_str(it.payload, cfg.problem_text_keys)
            atxt = _first_str(it.payload, cfg.ask_line_keys)
            if ptxt:
                st.markdown(ptxt)
            if atxt:
                st.markdown(f"> {atxt}")

        with cols[2]:
            # 난이도
            cur = state.difficulty.get(uid, "미분류")
            new = st.selectbox("난이도", cfg.difficulty_levels, index=cfg.difficulty_levels.index(cur), key=f"diff_{uid}_{page}_{idx}")
            state.difficulty[uid] = new

        # 제시표 렌더
        given = try_find_table(it.payload, list(cfg.given_table_keys))
        if given is not None:
            with st.expander("표 보기", expanded=False):
                render_table_pretty(given)

        st.divider()

def _first_str(payload, keys):
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None