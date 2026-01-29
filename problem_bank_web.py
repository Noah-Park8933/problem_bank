import streamlit as st
from datetime import datetime

from problem_bank.config import AppConfig
from problem_bank.loader import load_all
from problem_bank.state_manager import ensure_state
from problem_bank.ui_filters import filter_items
from problem_bank.ui_sidebar import sidebar_actions
from problem_bank.ui_main import render_list
from problem_bank.docx_exporter import export_docx_bytes
from problem_bank.generator_ui import render_generator_panel
from problem_bank.history import HistoryStore  # ✅ 추가

from file_manager import render_file_manager


def main():
    st.set_page_config(page_title="Problem Bank", layout="wide")

    tabA, tabB, tabC = st.tabs(["문제은행", "문제 생성기", "Mount파일"])
    with tabA:
        st.write("update : 화학1 유형 추가, 물리1 유형 추가 예정(soon)")
    with tabB:
        render_generator_panel()
    with tabC:
        render_file_manager()
        st.write("cloud에 mount된 파일 확인용")

    cfg = AppConfig()
    state = ensure_state(st)

    # ✅ 히스토리(앱 재시작해도 유지)
    history = HistoryStore("data/history_export.json")

    st.title("수능 과학탐구 문제은행")

    with st.spinner("PACK 로딩 중..."):
        items = load_all(cfg)
    # ===== 중복 진단(여기!) =====
    from collections import Counter

    uids = [it.uid for it in items]
    c = Counter(uids)
    dups = [(uid, n) for uid, n in c.items() if n > 1]

    st.write("총 items:", len(items))
    st.write("고유 uid:", len(set(uids)))
    st.write("중복 uid 개수:", len(dups))

    if dups:
        st.write("중복 uid 예시(앞 20개):", dups[:20])
# ===========================

st.caption(f"전체 로드: {len(items)}개")
st.caption(f"전체 로드: {len(items)}개")

    filtered, meta = filter_items(cfg, items)

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
    # 페이지네이션
    # -----------------------------
    total_pages = max(1, (len(filtered) + cfg.page_size - 1) // cfg.page_size)
    page = st.sidebar.number_input("페이지", min_value=1, max_value=total_pages, value=1, step=1) - 1

    # 현재 화면 uid 목록
    start = page * cfg.page_size
    end = min(len(filtered), start + cfg.page_size)
    visible_uids = [it.uid for it in filtered[start:end]]

    sidebar_actions(state, visible_uids)

    # -----------------------------
    # 내보내기(선택 문항)
    # -----------------------------
    st.sidebar.subheader("내보내기")
    include_expl = st.sidebar.checkbox("해설 포함", value=True)
    include_full = st.sidebar.checkbox("완성표 포함", value=True)
    two_col = st.sidebar.checkbox("2단(페이지당 2문항)", value=True)

    selected_items = [it for it in filtered if it.uid in state.selected_uids]

    if st.sidebar.button("선택 문항 DOCX 생성"):
        if not selected_items:
            st.sidebar.warning("선택된 문항이 없습니다.")
        else:
            docx_bytes = export_docx_bytes(
                cfg=cfg,
                selected=selected_items,
                include_explanations=include_expl,
                include_full_table=include_full,
                two_columns=two_col,
            )

            docx_name = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

            # ✅ bytes는 세션에 저장해두면 download_button이 안정적으로 뜸
            st.session_state["_last_docx_bytes"] = docx_bytes
            st.session_state["_last_docx_name"] = docx_name

            # ✅ "DOCX 추출 성공 시점"에만 history 저장
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

            st.sidebar.success(f"DOCX 생성 완료: {len(selected_items)}문항")

    if st.session_state.get("_last_docx_bytes"):
        st.sidebar.download_button(
            label="DOCX 다운로드",
            data=st.session_state["_last_docx_bytes"],
            file_name=st.session_state.get("_last_docx_name", "export.docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    # -----------------------------
    # 메인 리스트
    # -----------------------------
    st.subheader(f"표시 중: {len(filtered)}개 / 전체: {len(items)}개")

    # ✅ render_list에 history 전달(시그니처 변경 반영)
    render_list(cfg, state, history, filtered, page)


if __name__ == "__main__":
    main()
