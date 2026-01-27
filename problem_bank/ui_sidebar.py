import streamlit as st
from .state_manager import AppState

def sidebar_actions(state: AppState, visible_uids: list[str]):
    st.sidebar.subheader("선택")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("현재 화면 전체선택"):
        for uid in visible_uids:
            state.selected_uids.add(uid)
    if c2.button("현재 화면 전체해제"):
        for uid in visible_uids:
            state.selected_uids.discard(uid)

    st.sidebar.write(f"선택: {len(state.selected_uids)}개")