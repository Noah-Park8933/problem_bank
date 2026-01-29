# ============================================
# generator_ui.py
# Streamlit에서 생성기별 PACK 자동 생성 패널
# ============================================

import os
import streamlit as st

# ============================================================
# 1) 생성기 import (여기만 네 환경에 맞게 수정하면 됨)
# ============================================================
# TODO — 실제 파일명 & 함수명으로 교체해야 함
from matrix3_generator_PACK import make_pack as make_pack_matrix3
# from division_generator_PACK_NOXINFO_randomX12_hiddenX_v4 import make_pack as make_pack_division
# from DNA_integration_generator import make_pack as make_pack_dna
# from PDED1_generator import make_pack as make_pack_pded1
# from PCCC1_generator import make_pack as make_pack_pccc1
from matrix4_generator_PACK import make_pack as make_pack_matrix4
# ...

# ============================================================
# 2) 생성기 목록 (여기에 원하는 생성기 추가)
# ============================================================
GENERATORS = [
    {
        "key": "MATRIX3",
        "title": "🧬 Matrix3 문제 자동 생성",
        "default_n": 30,
        "min_n": 1,
        "max_n": 200,
        "run": lambda n: make_pack_matrix3(n=n),
    },
    {
        "key": "MATRIX4",
        "title": "🧬 Matrix4 문제 자동 생성",
        "default_n": 30,
        "min_n": 1,
        "max_n": 200,
        "run": lambda n: make_pack_matrix4(n=n),
    },

    # 예시 — 필요하면 주석 해제 후 파일 연결
    # {
    #     "key": "DIVISION",
    #     "title": "🌳 Division 문제 자동 생성",
    #     "default_n": 30,
    #     "min_n": 1,
    #     "max_n": 200,
    #     "run": lambda n: make_pack_division(n=n),
    # },
]


    # 예시 — 필요하면 주석 해제 후 파일 연결
    # {
    #     "key": "DIVISION",
    #     "title": "🌳 Division 문제 자동 생성",
    #     "default_n": 30,
    #     "min_n": 1,
    #     "max_n": 200,
    #     "run": lambda n: make_pack_division(n=n),
    # },
# ]


# ============================================================
# 3) 파일 다운로드 헬퍼
# ============================================================
def _download_file(path: str, label: str):
    if not path or not os.path.exists(path):
        st.error(f"파일을 찾을 수 없습니다: {path}")
        return
    with open(path, "rb") as f:
        st.download_button(
            label=label,
            data=f,
            file_name=os.path.basename(path),
            mime="application/json",
            use_container_width=True
        )


# ============================================================
# 4) 생성기 UI 메인 함수
# ============================================================
def render_generator_panel():
    st.subheader("⚡ 문제 자동 생성 (Generator Panel)")

    tabs = st.tabs([g["key"] for g in GENERATORS])

    for tab, gen in zip(tabs, GENERATORS):
        with tab:
            st.markdown(f"### {gen['title']}")

            n = st.number_input(
                "생성할 문항 수",
                min_value=gen["min_n"],
                max_value=gen["max_n"],
                value=gen["default_n"],
                step=1,
                key=f"n_{gen['key']}"
            )

            make_btn = st.button(
                f"📦 {gen['key']} PACK 생성",
                key=f"btn_{gen['key']}",
                use_container_width=True
            )

            if make_btn:
                with st.spinner(f"{gen['key']} 생성 중..."):
                    try:
                        out_path = gen["run"](int(n))
                        st.success("생성 성공!")
                        st.code(out_path)
                        _download_file(out_path, "📥 PACK 다운로드")
                    except Exception as e:
                        st.error("생성 실패")
                        st.code(str(e))


# ============================================================
# 5) 독립 실행 가능하도록 옵션
# ============================================================
def main():
    st.set_page_config(page_title="문제 자동 생성기", layout="wide")
    st.title("📌 문제 자동 생성기 패널")
    render_generator_panel()


if __name__ == "__main__":
    main()
