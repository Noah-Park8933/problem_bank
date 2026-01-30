# HJHMPHYSICS1_photoelectric_pack_generator_DBSTYLE.py
# ------------------------------------------------------------
# 문제은행 DB(BLOODG 스타일) 호환 pack exporter
#  - 최상위: {module, id_prefix, created_at, items:[...]}
#  - 각 item: {id,module,id_prefix,difficulty,problem_text_md,...,payload:{...}}
#  - payload 안에 실문항 필드(problem_text_md/ask_line_md/table_md/full_table_md/answer_md/explanation_md/meta/_qnum)
# ------------------------------------------------------------

from __future__ import annotations
import json
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional


# ----------------------------
# 고정 설정
# ----------------------------
MODULE = "HJHMPHYSICS1"
ID_PREFIX = "HJHMPHYSICS1_"   # ✅ 성공 예시처럼 '_' 포함


# ----------------------------
# ㄱㄴㄷ 고르는 5지(문제은행 예시 형식과 동일)
# ----------------------------
CHOICE_TEXT = "① ㄱ ② ㄴ ③ ㄱ, ㄷ ④ ㄴ, ㄷ ⑤ ㄱ, ㄴ, ㄷ"


def safe_randint(rng: random.Random, lo: int, hi: int) -> int:
    if lo > hi:
        raise ValueError(f"empty range: lo={lo}, hi={hi}")
    return rng.randint(lo, hi)


@dataclass
class PhotoProblem:
    n: int
    m: int
    k: int
    A: int
    B: int
    C: int
    D: int
    g_truth: bool
    n_truth: bool
    d_truth: bool


def render_table_md(p: PhotoProblem) -> str:
    return (
        "| 금속판 | 단색광 | 최대 운동 에너지 |\n"
        "|---|---:|---:|\n"
        f"| P | {p.n}f₀ | {p.A}E₀ |\n"
        f"| P | {p.m}f₀ | {p.B}E₀ |\n"
        f"| Q | {p.n}f₀ | {p.C}E₀ |\n"
        f"| Q | {p.m}f₀ | ① |\n"
    )


def generate_one(rng: random.Random) -> PhotoProblem:
    # 진동수 배수 선택
    n = safe_randint(rng, 1, 6)
    delta = rng.choice([1, 2, 3])
    m = n + delta
    if m > 9:
        n, m = 7, 9

    # hf0 = kE0
    k = rng.choice([1, 2, 3, 4])
    diff = (m - n) * k
    if diff > 8:
        k = rng.choice([1, 2])
        diff = (m - n) * k
        if diff > 8:
            return generate_one(rng)

    # A,C는 1~9-diff
    max_base = 9 - diff
    if max_base < 1:
        return generate_one(rng)

    A = safe_randint(rng, 1, max_base)
    C = safe_randint(rng, 1, max_base)
    B = A + diff
    D = C + diff

    # ㄱ: "문턱 진동수는 P가 Q보다 크다." ↔ A < C
    g_truth = (A < C)

    # ㄴ, ㄷ truth 랜덤 (문장 생성에서 참/거짓 유지)
    n_truth = rng.choice([True, False])
    d_truth = rng.choice([True, False])

    return PhotoProblem(n, m, k, A, B, C, D, g_truth, n_truth, d_truth)


def truths_to_answer_index(g: bool, n: bool, d: bool) -> int:
    """
    문제은행이 쓰는 고정 5지:
      ① ㄱ
      ② ㄴ
      ③ ㄱ, ㄷ
      ④ ㄴ, ㄷ
      ⑤ ㄱ, ㄴ, ㄷ
    에 맞춰 정답 번호 리턴.
    """
    if g and not n and not d:
        return 1
    if (not g) and n and (not d):
        return 2
    if g and (not n) and d:
        return 3
    if (not g) and n and d:
        return 4
    if g and n and d:
        return 5
    # 위 5개 외 조합은 이 형식의 선택지로 표현 불가 → 이런 경우는 버리고 재생성
    return 0


def build_one_payload(rng: random.Random, pid: str, qnum: int, difficulty: int = 1) -> Optional[Dict[str, Any]]:
    p = generate_one(rng)

    # ㄴ 문장 생성(참/거짓 유지) + B==9 방어
    if p.n_truth:
        y = safe_randint(rng, 1, p.B)
        n_sentence = f"P에 진동수가 {p.m}f₀인 빛을 비추면 방출되는 광전자의 최대 운동 에너지는 {y}E₀ 이상이다."
    else:
        if p.B < 9:
            y = safe_randint(rng, p.B + 1, 9)
            n_sentence = f"P에 진동수가 {p.m}f₀인 빛을 비추면 방출되는 광전자의 최대 운동 에너지는 {y}E₀ 이상이다."
        else:
            # B=9이면 '이상이다'로 거짓 만들 수 없으니 '미만이다'로 거짓 확정
            y = 1
            n_sentence = f"P에 진동수가 {p.m}f₀인 빛을 비추면 방출되는 광전자의 최대 운동 에너지는 {y}E₀ 미만이다."

    # ㄷ 문장
    if p.d_truth:
        d_sentence = f"①은 {p.D}E₀이다."
    else:
        wrong = [i for i in range(1, 10) if i != p.D]
        t = rng.choice(wrong)
        d_sentence = f"①은 {t}E₀이다."

    ask_line_md = (
        "이에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?\n\n"
        "<보 기>\n"
        "ㄱ. 문턱 진동수는 P가 Q보다 크다.\n"
        f"ㄴ. {n_sentence}\n"
        f"ㄷ. {d_sentence}\n\n"
        f"{CHOICE_TEXT}"
    )

    # 정답 번호 계산(고정 선택지 5개에 포함되는 조합만 허용)
    ans = truths_to_answer_index(p.g_truth, p.n_truth, p.d_truth)
    if ans == 0:
        return None  # 표현 불가능 조합 → 재생성

    table_md = render_table_md(p)

    problem_text_md = (
        "표는 금속판 P, Q에 단색광을 비추었을 때 방출되는 광전자의 최대 운동 에너지를 "
        "단색광의 진동수에 따라 나타낸 것이다."
    )

    explanation_md = (
        f"P에서 {p.n}f₀→{p.m}f₀로 증가할 때 K 변화량은 {p.B - p.A}E₀이고, "
        f"Q에서도 동일하므로 ①={p.C}E₀+{p.B - p.A}E₀={p.D}E₀이다.\n"
        f"따라서 (ㄱ, ㄴ, ㄷ)=({str(p.g_truth)}, {str(p.n_truth)}, {str(p.d_truth)}) 이고 정답은 {ans}이다."
    )

    # ✅ BLOODG 스타일 item
    item = {
        "id": pid,
        "module": MODULE,
        "id_prefix": ID_PREFIX,
        "difficulty": difficulty,
        # 상위 카드용 필드는 비워도 되지만, 안전하게 간단히 채움
        "problem_text_md": "",
        "ask_line_md": "",
        "answer_text_md": "",
        "solution_md": "",
        "payload": {
            "problem_text_md": problem_text_md,
            "ask_line_md": ask_line_md,
            "table_md": table_md,
            "full_table_md": table_md,
            "answer_md": f"**정답:** {ans}",
            "explanation_md": explanation_md,
            "meta": {
                "truths": [p.g_truth, p.n_truth, p.d_truth],
                "A": p.A, "B": p.B, "C": p.C, "D": p.D,
                "n": p.n, "m": p.m, "k": p.k,
            },
            "_qnum": qnum,
        }
    }
    return item


def make_pack(n_items: int = 30, seed: int = 18, difficulty: int = 1,
              out_path: str = "HJHMPHYSICS1_photoelectric_DBSTYLE.json") -> Dict[str, Any]:
    rng = random.Random(seed)
    items: List[Dict[str, Any]] = []

    tries = 0
    while len(items) < n_items:
        tries += 1
        if tries > n_items * 500:
            raise RuntimeError("생성 실패: tries 초과(조건을 너무 빡세게 잡음)")

        qnum = len(items) + 1
        pid = f"{ID_PREFIX}{seed:04d}_{qnum:03d}"  # 예: HJHMPHYSICS1_0018_001

        it = build_one_payload(rng, pid, qnum=qnum, difficulty=difficulty)
        if it is None:
            continue

        # 한 자리 자연수 검증
        meta = it["payload"]["meta"]
        if not all(1 <= meta[x] <= 9 for x in ["A", "B", "C", "D"]):
            continue

        items.append(it)

    pack = {
        "module": MODULE,
        "id_prefix": ID_PREFIX,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "items": items,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)

    return pack


if __name__ == "__main__":
    pack = make_pack(n_items=30, seed=18, difficulty=1,
                     out_path="HJHMPHYSICS1_photoelectric_DBSTYLE.json")
    print(f"OK: {len(pack['items'])} items saved -> HJHMPHYSICS1_photoelectric_DBSTYLE.json")
    print("sample id:", pack["items"][0]["id"])
