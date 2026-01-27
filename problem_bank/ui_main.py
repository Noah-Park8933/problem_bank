# problem_bank/ui_main.py
import streamlit as st
from typing import List

from .loader import load_all, ProblemItem
from .config import AppConfig
from .state_manager import AppState

from .table_renderer import try_find_table, normalize_table_to_grid


# -----------------------------
# UI helpers
# -----------------------------
def _ensure_state() -> AppState:
    if "app_state" not in st.session_state:
        st.session_state.app_state = AppState()
    return st.session_state.app_state


def _first_str(payload, keys):
    if not isinstance(payload, dict):
        return None
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def render_table_pretty(table_obj):
    headers, rows = normalize_table_to_grid(table_obj)

    if not headers or not rows:
        st.write("(표 없음)")
        return

    # pandas 안전 변환(열/행 길이 불일치 방지)
    import pandas as pd

    max_len = max(len(headers), *(len(r) for r in rows))
    headers = headers + [""] * (max_len - len(headers))

    fixed_rows = []
    for r in rows:
        fixed_rows.append(r + [""] * (max_len - len(r)))

    df = pd.DataFrame(fixed_rows, columns=headers)
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
            new_checked = st.checkbox(
                " ",
                value=checked,
                key=f"chk_{uid}_{page}_{idx}",
            )
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
            else:
                # fallback: payload 안에 problem_text_md가 payload 내부에도 있을 수 있음
                ptxt2 = None
                if isinstance(it.payload, dict):
                    ptxt2 = it.payload.get("problem_text_md")
                    if isinstance(ptxt2, str) and ptxt2.strip():
                        st.markdown(ptxt2.strip())

            if atxt:
                st.markdown(f"> {atxt}")
            else:
                atxt2 = None
                if isinstance(it.payload, dict):
                    atxt2 = it.payload.get("ask_line_md")
                    if isinstance(atxt2, str) and atxt2.strip():
                        st.markdown(f"> {atxt2.strip()}")

        with cols[2]:
            cur = state.difficulty.get(uid, "미분류")
            if cur not in cfg.difficulty_levels:
                cur = "미분류"
            new = st.selectbox(
                "난이도",
                cfg.difficulty_levels,
                index=cfg.difficulty_levels.index(cur),
                key=f"diff_{uid}_{page}_{idx}",
            )
            state.difficulty[uid] = new

        # 제시표 렌더
        given = try_find_table(it.payload, list(cfg.given_table_keys))
        if given is not None:
            with st.expander("표 보기", expanded=False):
                render_table_pretty(given)

        st.divider()


# -----------------------------
# Filtering / paging
# -----------------------------
def _collect_prefixes(items: List[ProblemItem]) -> List[str]:
    return sorted({it.prefix for it in items if it.prefix})


def _collect_modules(items: List[ProblemItem]) -> List[str]:
    return sorted({it.module for it in items if it.module})


def _apply_filters(cfg: AppConfig, state: AppState, items: List[ProblemItem]) -> List[ProblemItem]:
    filtered = items

    # 선택만 보기
    if state.view_selected_only:
        filtered = [it for it in filtered if it.uid in state.selected_uids]

    # 모듈 필터
    if state.filter_module and state.filter_module != "전체":
        filtered = [it for it in filtered if it.module == state.filter_module]

    # prefix 필터
    if state.filter_prefix and state.filter_prefix != "전체":
        filtered = [it for it in filtered if it.prefix == state.filter_prefix]

    # 난이도 필터
    if state.filter_difficulty and state.filter_difficulty != "전체":
        want = state.filter_difficulty
        filtered = [it for it in filtered if state.difficulty.get(it.uid, "미분류") == want]

    # 검색(본문/요구사항/ID/prefix/module)
    q = (state.search_query or "").strip().lower()
    if q:
        out = []
        for it in filtered:
            pid = (it.pid or "").lower()
            prefix = (it.prefix or "").lower()
            module = (it.module or "").lower()

            ptxt = _first_str(it.payload, cfg.problem_text_keys) or ""
            atxt = _first_str(it.payload, cfg.ask_line_keys) or ""
            # fallback keys
            if isinstance(it.payload, dict):
                ptxt = ptxt or (it.payload.get("problem_text_md") or "")
                atxt = atxt or (it.payload.get("ask_line_md") or "")

            blob = " ".join([pid, prefix, module, str(ptxt), str(atxt)]).lower()
            if q in blob:
                out.append(it)
        filtered = out

    return filtered


# -----------------------------
# Data loading (cached)
# -----------------------------
@st.cache_data(show_spinner=False)
def _load_items_cached(cfg_dict: dict) -> List[ProblemItem]:
    # cfg 자체는 dataclass일 수 있어서 dict로 받아 캐시 안정화
    cfg = AppConfig(**cfg_dict)
    return load_all(cfg)


def _cfg_to_dict(cfg: AppConfig) -> dict:
    # AppConfig가 dataclass라고 가정
    return {k: getattr(cfg, k) for k in cfg.__dataclass_fields__.keys()}


# -----------------------------
# Main
# -----------------------------
def main():
    st.set_page_config(page_title="Problem Bank", layout="wide")
    st.title("문제은행")

    cfg = AppConfig()  # 너가 config.py에서 관리
    state = _ensure_state()

    # 상단 툴바
    top = st.columns([0.18, 0.18, 0.18, 0.18, 0.28])
    with top[0]:
        if st.button("🔄 새로고침(재로드)"):
            # cache 무효화 + 선택 유지
            st.cache_data.clear()
            st.rerun()
    with top[1]:
        if st.button("✅ 전체 선택(현재 필터)"):
            # 필터 결과 전체 선택
            items = _load_items_cached(_cfg_to_dict(cfg))
            filtered = _apply_filters(cfg, state, items)
            for it in filtered:
                state.selected_uids.add(it.uid)
            st.rerun()
    with top[2]:
        if st.button("🧹 전체 해제(현재 필터)"):
            items = _load_items_cached(_cfg_to_dict(cfg))
            filtered = _apply_filters(cfg, state, items)
            for it in filtered:
                state.selected_uids.discard(it.uid)
            st.rerun()
    with top[3]:
        state.view_selected_only = st.toggle("선택만 보기", value=bool(state.view_selected_only))
    with top[4]:
        state.search_query = st.text_input("검색", value=state.search_query or "", placeholder="ID / prefix / 본문 / 요구사항 검색")

    # 데이터 로드
    items = _load_items_cached(_cfg_to_dict(cfg))

    # 좌측 필터 영역
    st.subheader("필터")
    fcols = st.columns([0.25, 0.25, 0.25, 0.25])

    modules = ["전체"] + _collect_modules(items)
    prefixes = ["전체"] + _collect_prefixes(items)

    with fcols[0]:
        if state.filter_module not in modules:
            state.filter_module = "전체"
        state.filter_module = st.selectbox("모듈", modules, index=modules.index(state.filter_module))

    with fcols[1]:
        if state.filter_prefix not in prefixes:
            state.filter_prefix = "전체"
        state.filter_prefix = st.selectbox("ID prefix", prefixes, index=prefixes.index(state.filter_prefix))

    with fcols[2]:
        diffs = ["전체"] + list(cfg.difficulty_levels)
        if state.filter_difficulty not in diffs:
            state.filter_difficulty = "전체"
        state.filter_difficulty = st.selectbox("난이도 필터", diffs, index=diffs.index(state.filter_difficulty))

    with fcols[3]:
        st.caption(f"로드: {len(items)}개 / 선택: {len(state.selected_uids)}개")

    # 필터 적용
    filtered = _apply_filters(cfg, state, items)

    # 페이지네이션
    total = len(filtered)
    if total == 0:
        st.warning("표시할 문제가 없습니다. (필터/검색/로드 경로 확인)")
        return

    max_page = (total - 1) // cfg.page_size
    pcols = st.columns([0.2, 0.6, 0.2])
    with pcols[0]:
        if st.button("⬅️ 이전"):
            state.page = max(0, int(state.page or 0) - 1)
            st.rerun()
    with pcols[1]:
        state.page = st.slider("페이지", 0, max_page, int(state.page or 0))
    with pcols[2]:
        if st.button("다음 ➡️"):
            state.page = min(max_page, int(state.page or 0) + 1)
            st.rerun()

    st.caption(f"표시 중: {state.page * cfg.page_size + 1} ~ {min(total, (state.page + 1) * cfg.page_size)} / 전체 {total}")

    # 리스트 렌더
    st.subheader("문항 목록")
    render_list(cfg, state, filtered, int(state.page or 0))


if __name__ == "__main__":
    main()