# problem_bank/ui_main.py
import os
from datetime import datetime
from typing import List

import streamlit as st

from .loader import load_all, ProblemItem
from .config import AppConfig
from .state_manager import AppState

from .table_renderer import try_find_table, normalize_table_to_grid, normalize_tables_to_grids
from .docx_exporter import export_docx_bytes
from .history import HistoryStore


# -----------------------------
# UI helpers
# -----------------------------
def _make_unique_headers(headers):
    seen = {}
    out = []
    for h in headers:
        name = "" if h is None else str(h)
        name = name.strip()
        if name == "":
            name = "(blank)"
        cnt = seen.get(name, 0)
        if cnt == 0:
            out.append(name)
        else:
            out.append(f"{name}_{cnt+1}")
        seen[name] = cnt + 1
    return out


def render_tables_pretty(table_obj):
    headers, rows = normalize_table_to_grid(table_obj)

    if not headers or rows is None:
        st.write("(표 없음)")
        return

    import pandas as pd

    # rows가 비어있으면 표 없음 처리
    if not isinstance(rows, list) or len(rows) == 0:
        st.write("(표 없음)")
        return

    # 열/행 길이 불일치 방어
    max_len = max(len(headers), *(len(r) for r in rows))
    headers = list(headers) + [""] * (max_len - len(headers))

    fixed_rows = []
    for r in rows:
        r = list(r) if r is not None else []
        fixed_rows.append(r + [""] * (max_len - len(r)))

    # ✅ 1차: 헤더 유일화
    headers = _make_unique_headers(headers)

    df = pd.DataFrame(fixed_rows, columns=headers)

    # ✅ 2차: 혹시라도 남아있으면 강제 유일화(최후 방어)
    if df.columns.duplicated().any():
        df.columns = _make_unique_headers(list(df.columns))

    st.dataframe(df, use_container_width=True)


def try_find_image(payload):
    if not isinstance(payload, dict):
        return None

    # loader.normalize_images가 "_image_path"로도 넣어주므로 이것도 포함
    keys = ["_image_path", "image", "img", "figure", "image_path", "img_path", "tree_img", "fig_path", "figure_path", "diagram_file"]
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and v.strip() and os.path.exists(v.strip()):
            return v.strip()
    return None


def render_list(
    cfg: AppConfig,
    state: AppState,
    history: HistoryStore,
    items: List[ProblemItem],
    page: int,
):
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
                key=f"chk_{uid}",  # ✅ page/idx 붙이면 페이지 이동 시 UI 꼬일 수 있음
            )
            if new_checked:
                state.selected_uids.add(uid)
            else:
                state.selected_uids.discard(uid)

        with cols[1]:
            st.markdown(f"**{it.pid}**  `({it.prefix})`")

            # ✅ DOCX 추출 여부 표시(선택이 아니라 '추출 기록'만)
            rec = history.get(uid)
            if rec:
                st.caption(f"📄 DOCX 추출됨 · {rec.exported_at} · {rec.docx_name}")

            # 본문/요구사항
            ptxt = _first_str(it.payload, cfg.problem_text_keys)
            atxt = _first_str(it.payload, cfg.ask_line_keys)

            if ptxt:
                st.markdown(ptxt)
            else:
                # fallback: payload 안에 problem_text_md
                if isinstance(it.payload, dict):
                    ptxt2 = it.payload.get("problem_text_md")
                    if isinstance(ptxt2, str) and ptxt2.strip():
                        st.markdown(ptxt2.strip())

            if atxt:
                st.markdown(f"> {atxt}")
            else:
                if isinstance(it.payload, dict):
                    atxt2 = it.payload.get("ask_line_md")
                    if isinstance(atxt2, str) and atxt2.strip():
                        st.markdown(f"> {atxt2.strip()}")

            # 이미지(있으면 아래에)
            img_path = try_find_image(it.payload)
            if img_path:
                with st.expander("이미지 보기", expanded=False):
                    st.image(img_path, use_container_width=True)

        with cols[2]:
            cur = state.difficulty.get(uid, "미분류")
            if cur not in cfg.difficulty_levels:
                cur = "미분류"
            new = st.selectbox(
                "난이도",
                cfg.difficulty_levels,
                index=cfg.difficulty_levels.index(cur),
                key=f"diff_{uid}",  # ✅ uid만 쓰는 게 안전
            )
            state.difficulty[uid] = new

        # 제시표 렌더 (복수 표 지원)
        given = try_find_table(it.payload, list(cfg.given_table_keys))
        if given is not None:
            with st.expander("표 보기", expanded=False):
                render_tables_pretty(given)

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
    cfg = AppConfig(**cfg_dict)
    return load_all(cfg)


def _cfg_to_dict(cfg: AppConfig) -> dict:
    return {k: getattr(cfg, k) for k in cfg.__dataclass_fields__.keys()}


# -----------------------------
# Main
# -----------------------------
def main():
    st.set_page_config(page_title="Problem Bank", layout="wide")
    st.title("문제은행")

    cfg = AppConfig()
    state = _ensure_state()
    history = HistoryStore("data/history_export.json")

    # -----------------------------
    # 상단 툴바
    # -----------------------------
    top = st.columns([0.18, 0.18, 0.18, 0.18, 0.28])
    with top[0]:
        if st.button("🔄 새로고침(재로드)"):
            st.cache_data.clear()
            st.rerun()

    with top[1]:
        if st.button("✅ 전체 선택(현재 필터)"):
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
        state.search_query = st.text_input(
            "검색",
            value=state.search_query or "",
            placeholder="ID / prefix / 본문 / 요구사항 검색",
        )

    # -----------------------------
    # 데이터 로드
    # -----------------------------
    items = _load_items_cached(_cfg_to_dict(cfg))

    # -----------------------------
    # 필터
    # -----------------------------
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
        st.caption(f"로드: {len(items)}개 / 선택: {len(state.selected_uids)}개 / 추출기록: {len(history.list_records())}개")

    # -----------------------------
    # 히스토리 패널(최근 추출 목록)
    # -----------------------------
    with st.expander("📚 최근 DOCX 추출 히스토리", expanded=False):
        recs = history.list_records()[:50]
        if not recs:
            st.write("추출 기록이 없습니다.")
        else:
            for r in recs:
                st.write(f"- **{r.pid}**  `({r.module})`")
                st.caption(f"{r.exported_at} · {r.docx_name}")
            c1, c2 = st.columns([0.2, 0.8])
            with c1:
                if st.button("🗑️ 히스토리 비우기"):
                    history.clear()
                    st.rerun()
            with c2:
                st.caption("※ 히스토리는 'DOCX로 실제 추출된 문항'만 저장됩니다.")

    # -----------------------------
    # 내보내기 (선택된 문항만)
    # -----------------------------
    st.subheader("내보내기")
    ecols = st.columns([0.18, 0.18, 0.18, 0.18, 0.28])

    with ecols[0]:
        include_expl = st.toggle("해설 포함", value=True)
    with ecols[1]:
        include_full = st.toggle("완성표 포함", value=True)
    with ecols[2]:
        two_cols = st.toggle("2단", value=True)
    with ecols[3]:
        # 최근 생성된 DOCX를 초기화하고 싶으면
        if st.button("🧼 DOCX 상태 초기화"):
            st.session_state.pop("_last_docx_bytes", None)
            st.session_state.pop("_last_docx_name", None)
            st.rerun()

    with ecols[4]:
        if st.button("📄 DOCX 생성(선택 문항)"):
            selected_items = [it for it in items if it.uid in state.selected_uids]
            if not selected_items:
                st.warning("선택된 문항이 없습니다.")
            else:
                docx_bytes = export_docx_bytes(
                    cfg=cfg,
                    selected=selected_items,
                    include_explanations=include_expl,
                    include_full_table=include_full,
                    two_columns=two_cols,
                )

                docx_name = f"problemset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                st.session_state["_last_docx_bytes"] = docx_bytes
                st.session_state["_last_docx_name"] = docx_name

                # ✅ "추출 성공 시점"에만 history 기록
                for it in selected_items:
                    history.add_export(
                        uid=it.uid,
                        pid=it.pid,
                        module=it.module,
                        pack_path=it.path,
                        docx_name=docx_name,
                        docx_bytes=docx_bytes,
                        docx_path="",
                        meta={"prefix": it.prefix},
                    )

                st.success(f"DOCX 생성 완료: {len(selected_items)}문항")

    if st.session_state.get("_last_docx_bytes"):
        st.download_button(
            "⬇️ DOCX 다운로드",
            data=st.session_state["_last_docx_bytes"],
            file_name=st.session_state.get("_last_docx_name", "problems.docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    # -----------------------------
    # 필터 적용 + 페이지네이션
    # -----------------------------
    filtered = _apply_filters(cfg, state, items)

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

    # -----------------------------
    # 리스트 렌더
    # -----------------------------
    st.subheader("문항 목록")
    render_list(cfg, state, history, filtered, int(state.page or 0))


if __name__ == "__main__":
    main()
