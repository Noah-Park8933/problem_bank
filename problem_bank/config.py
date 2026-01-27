from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class AppConfig:
    # PACK json들이 있는 폴더(들)
    data_dirs: List[str] = ("output", "packs", ".")

    # 로딩 제한(너가 말한 150 제한 같은 거)
    max_load: int = 5000

    # 미리보기/목록 한 페이지
    page_size: int = 50

    # 난이도 라벨
    difficulty_levels: List[str] = ("미분류", "하", "중", "상", "극상")

    # table 키 후보(여기 확장하면 됨)
    given_table_keys: List[str] = (
        "masked_table", "given_table", "table", "grid", "matrix", "prompt_table",
        "given", "masked"
    )
    full_table_keys: List[str] = (
        "full_table", "answer_table", "solution_table", "complete_table",
        "full", "complete"
    )

    # 본문/요구사항 텍스트 후보 키
    problem_text_keys: List[str] = ("problem_text_md", "problem_md", "problem_text", "stem", "question")
    ask_line_keys: List[str] = ("ask_line_md", "ask_md", "ask", "tasks", "request")
    answer_keys: List[str] = ("answer_md", "answer", "ans", "answer_num", "correct", "answer_text_md")
    explanation_keys: List[str] = ("explanation_md", "explain_md", "explanation", "solution", "reasons", "commentary")

    # 이미지 키 후보 (Division tree 같은 거)
    image_keys: List[str] = ("image_path", "figure_path", "img", "png", "figure")
