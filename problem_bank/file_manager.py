# file_manager.py
import streamlit as st
from pathlib import Path
import time

def render_file_manager():
    st.subheader("📁 Mount 파일 관리자")

    # mount 경로 자동 탐지
    candidates = [Path("/mount/src/problem_bank/output_pack")]
    mount_dir = next((p for p in candidates if p.exists()), candidates[0])

    st.write(f"관리 대상: `{mount_dir}`")

    if not mount_dir.exists():
        st.error("마운트 경로가 존재하지 않습니다.")
        return

    files = [p for p in mount_dir.iterdir() if p.is_file()]
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    st.write(f"총 파일: {len(files)}개")
    st.write("---")

    selected = []
    for p in files:
        if st.checkbox(f"{p.name} — {p.stat().st_size} bytes", key=str(p)):
            selected.append(p)

    st.write("---")
    if st.button("🗑 선택 파일 삭제"):
        if not selected:
            st.warning("선택된 파일이 없습니다.")
            return
        for p in selected:
            try:
                p.unlink()
            except Exception as e:
                st.error(f"{p.name} 삭제 실패: {e}")
        st.success("삭제 완료!")
