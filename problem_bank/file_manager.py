# file_manager.py
import streamlit as st
from pathlib import Path

# ▼ 너네 앱에서 실제로 파일이 저장되는 경로로 바꿔
# 보통 Streamlit Community Cloud에서는 /mnt/data가 기본
MOUNT_DIR = Path("/mount/data")  # ← 필요하면 /mnt/data 로 수정 필요

def list_files():
    if not MOUNT_DIR.exists():
        st.error(f"경로 없음: {MOUNT_DIR}")
        return []

    files = sorted(
        [p for p in MOUNT_DIR.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return files

def delete_files(selected):
    deleted = []
    for p in selected:
        try:
            p.unlink()
            deleted.append(p.name)
        except Exception as e:
            st.warning(f"{p.name} 삭제 실패: {e}")
    return deleted


# ----------------------------
# Streamlit UI 시작
# ----------------------------
st.title("📁 Mount 파일 관리자")
st.write(f"**관리 대상 디렉토리:** `{MOUNT_DIR}`")

files = list_files()

if files:
    st.write(f"총 파일: **{len(files)}개**")
    st.write("---")

    selected_files = []
    for p in files:
        checked = st.checkbox(
            f"{p.name} — {p.stat().st_size} bytes",
            key=f"{p}"
        )
        if checked:
            selected_files.append(p)

    st.write("---")

    if st.button("🗑 선택된 파일 삭제"):
        if not selected_files:
            st.warning("선택된 파일이 없습니다.")
        else:
            deleted = delete_files(selected_files)
            st.success(f"삭제 완료: {len(deleted)}개")
            if deleted:
                st.code("\n".join(deleted))
else:
    st.info("마운트된 파일이 없습니다.")
