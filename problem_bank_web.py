import streamlit as st
from problem_bank.config import AppConfig
from problem_bank.loader import load_all, ProblemItem
from problem_bank.state_manager import ensure_state
from problem_bank.ui_filters import filter_items
from problem_bank.ui_sidebar import sidebar_actions
from problem_bank.ui_main import render_list
from problem_bank.docx_exporter import export_docx_bytes
from problem_bank.generator_ui import render_generator_panel
from file_manager import list_files

def main():

    st.set_page_config(page_title="Problem Bank", layout="wide")

    tabA, tabB, tabC = st.tabs(["문제은행", "문제 생성기", "Mount파일"])
    with tabA:
        st.write("update : Matrix 3 정상 작동, Matrix 4 개발중")
        # 기존 UI 함수 호출
    with tabB:
        render_generator_panel()
    with tabC:
        list_files()
        st.write("cloud에 mount된 파일 확인용")
    cfg = AppConfig()
    state = ensure_state(st)


    st.title("Life Science 1 문제 생성 DB")

    with st.spinner("PACK 로딩 중..."):
        items = load_all(cfg)

    st.caption(f"전체 로드: {len(items)}개")

    filtered, meta = filter_items(cfg, items)

    # 페이지네이션
    total_pages = max(1, (len(filtered) + cfg.page_size - 1) // cfg.page_size)
    page = st.sidebar.number_input("페이지", min_value=1, max_value=total_pages, value=1, step=1) - 1

    # 현재 화면 uid 목록
    start = page * cfg.page_size
    end = min(len(filtered), start + cfg.page_size)
    visible_uids = [it.uid for it in filtered[start:end]]

    sidebar_actions(state, visible_uids)

    # 내보내기
    st.sidebar.subheader("내보내기")
    include_expl = st.sidebar.checkbox("해설 포함", value=True)
    include_full = st.sidebar.checkbox("완성표 포함", value=True)
    two_col = st.sidebar.checkbox("2단(페이지당 2문항)", value=True)
   
    selected_items = [it for it in filtered if it.uid in state.selected_uids]
    if st.sidebar.button("선택 문항 DOCX 다운로드"):
        if not selected_items:
            st.sidebar.warning("선택된 문항이 없습니다.")
        else:
            docx_bytes = export_docx_bytes(cfg, selected_items, include_expl, include_full, two_columns=two_col)
            st.sidebar.download_button(
                label="DOCX 다운로드",
                data=docx_bytes,
                file_name="export.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

    # 메인 리스트
    st.subheader(f"표시 중: {len(filtered)}개 / 전체: {len(items)}개")
    render_list(cfg, state, filtered, page)

if __name__ == "__main__":
    main()
