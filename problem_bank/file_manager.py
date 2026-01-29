# file_manager.py
import streamlit as st
from pathlib import Path
import time

# 삭제 허용 확장자 (원하는 것만 남겨)
ALLOWED_EXT = {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".json", ".txt"}

def detect_mount_dir() -> Path:
    # Community Cloud에서 흔한 후보들
    candidates = [
        Path("/mnt/data"),
        Path("/mount/data"),
    ]
    for p in candidates:
        if p.exists():
            return p
    # 없으면 안전하게 아무 것도 못 하게 존재하지 않는 경로 반환
    return Path("/mnt/data")

def render_file_manager():
    st.subheader("📁 Mount 파일 관리자")

    mount_dir = detect_mount_dir()
    st.write(f"**관리 대상 디렉토리:** `{mount_dir}`")

    if not mount_dir.exists():
        st.error("마운트 경로가 존재하지 않습니다. (/mnt/data 또는 /mount/data 확인 필요)")
        return

    # 옵션: 오래된 파일만 보기
    max_age_hours = st.number_input("N시간보다 오래된 파일만 표시", min_value=0, max_value=720, value=0, step=1)
    name_filter = st.text_input("파일명 필터(포함 문자열)", value="")

    now = time.time()

    files = []
    for p in mount_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALLOWED_EXT:
            continue
        if name_filter and name_filter not in p.name:
            continue
        if max_age_hours > 0:
            age_sec = now - p.stat().st_mtime
            if age_sec < max_age_hours * 3600:
                continue
        files.append(p)

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    st.caption(f"표시 파일: {len(files)}개 (허용 확장자: {', '.join(sorted(ALLOWED_EXT))})")

    if not files:
        st.info("조건에 맞는 파일이 없습니다.")
        return

    st.write("---")

    selected = []
    for p in files:
        size = p.stat().st_size
        if st.checkbox(f"{p.name} — {size} bytes", key=f"fm_{p}"):
            selected.append(p)

    st.write("---")

    # 안전장치: 정말 삭제할 건지 체크
    confirm = st.checkbox("정말 삭제할게요 (체크해야 삭제 버튼 활성화)")

    if st.button("🗑 선택 파일 삭제", type="primary", disabled=not confirm):
        if not selected:
            st.warning("선택된 파일이 없습니다.")
            return

        deleted = []
        for p in selected:
            try:
                p.unlink()
                deleted.append(p.name)
            except Exception as e:
                st.error(f"{p.name} 삭제 실패: {e}")

        st.success(f"삭제 완료: {len(deleted)}개")
        if deleted:
            st.code("\n".join(deleted))
