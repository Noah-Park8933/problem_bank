# HJHMPHYSICS1_photoelectric_table_generator.py
# ------------------------------------------------------------
# 광전효과 표 기반 객관식 자동 문제 생성기 (안정화 최종본)
# ------------------------------------------------------------

from __future__ import annotations
import json
import random
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional


# ============================
#   문제은행 DB 설정
# ============================
MODULE = "HJHMPHYSICS1"
ID_PREFIX = "HJHMPHYSICS1"   # prefixid = id_prefix 동일


# ============================
#   선택지 구성 (5지)
# ============================
CHOICE_5: List[Tuple[str, ...]] = [
    ("ㄱ",),
    ("ㄴ",),
    ("ㄷ",),
    ("ㄱ", "ㄴ"),
    ("ㄴ", "ㄷ"),
]


def combo_to_str(combo: Tuple[str, ...]) -> str:
    return ", ".join(combo)


def safe_randint(rng: random.Random, lo: int, hi: int) -> int:
    """빈 구간 방지용 randint"""
    if lo > hi:
        raise ValueError(f"empty range: lo={lo}, hi={hi}")
    return rng.randint(lo, hi)


# ============================
#   문제 내부 데이터
# ============================
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


# ============================
#   표 렌더링
# ============================
def render_table_md(p: PhotoProblem) -> str:
    return (
        "| 금속판 | 단색광 | 최대 운동 에너지 |\n"
        "|---|---:|---:|\n"
        f"| P | {p.n}f₀ | {p.A}E₀ |\n"
        f"| P | {p.m}f₀ | {p.B}E₀ |\n"
        f"| Q | {p.n}f₀ | {p.C}E₀ |\n"
        f"| Q | {p.m}f₀ | ① |\n"
    )


# ============================
#   문항 생성 규칙 (안정화)
# ============================
def generate_one(rng: random.Random) -> PhotoProblem:
    # 1) 진동수 배수
    n = safe_randint(rng, 1, 6)
    delta = rng.choice([1, 2, 3])
    m = n + delta
    if m > 9:
        n, m = 7, 9

    # 2) hf0 = kE0
    k = rng.choice([1, 2, 3, 4])
    diff = (m - n) * k
    if diff > 8:
        k = rng.choice([1, 2])
        diff = (m - n) * k
        if diff > 8:
            return generate_one(rng)

    # 3) A, C 설정
    max_base = 9 - diff
    if max_base < 1:
        return generate_one(rng)

    A = safe_randint(rng, 1, max_base)
    C = safe_randint(rng, 1, max_base)
    B = A + diff
    D = C + diff

    # 4) ㄱ: 문턱 진동수 비교 → A < C 이면 참
    g_truth = (A < C)

    # 5) ㄴ: 참/거짓 먼저 결정
    n_truth = rng.choice([True, False])

    # 6) ㄷ: 참/거짓 먼저 결정
    d_truth = rng.choice([True, False])

    return PhotoProblem(n, m, k, A, B, C, D, g_truth, n_truth, d_truth)


# ============================
#   solver (정답 조합 유일성)
# ============================
def solve(p: PhotoProblem, n_truth: bool, d_truth: bool):
    truths = {"ㄱ": p.g_truth, "ㄴ": n_truth, "ㄷ": d_truth}

    correct = []
    for i, combo in enumerate(CHOICE_5, start=1):
        ok = True
        for k in ["ㄱ", "ㄴ", "ㄷ"]:
            if (k in combo) != truths[k]:
                ok = False
                break
        if ok:
            correct.append(i)

    return {
        "truths": truths,
        "options": [combo_to_str(c) for c in CHOICE_5],
        "correct_indices": correct,
        "is_unique": len(correct) == 1,
        "answer": correct[0] if len(correct) == 1 else None,
    }


# ============================
#   DB payload builder
# ============================
def to_problem_bank_payload(
    p: PhotoProblem,
    sol: Dict[str, Any],
    pid: str,
    n_sentence: str,
    d_sentence: str,
):
    table_md = render_table_md(p)

    problem_text_md = (
        "표는 금속판 P, Q에 단색광을 비추었을 때 방출되는 광전자의 최대 운동 에너지를 "
        "단색광의 진동수에 따라 나타낸 것이다."
    )

    ask_line_md = "이에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?"

    g_sentence = "문턱 진동수는 P가 Q보다 크다."

    view_md = (
        "<보기>\n"
        f"ㄱ. {g_sentence}\n"
        f"ㄴ. {n_sentence}\n"
        f"ㄷ. {d_sentence}\n"
    )

    choices_md = "\n".join(f"{i}. {s}" for i, s in enumerate(sol["options"], start=1))

    full_table_md = "\n\n".join([table_md, view_md, choices_md])

    explanation_md = (
        f"P에서 {p.n}f₀→{p.m}f₀로 증가할 때 K 변화량은 {p.B - p.A}E₀이며, "
        f"Q에서도 동일하여 ①은 {p.D}E₀가 된다.\n"
        f"따라서 ㄱ, ㄴ, ㄷ을 판단해 정답은 {sol['answer']}이다."
    )

    return {
        "id": pid,
        "module": MODULE,
        "prefixid": ID_PREFIX,
        "id_prefix": ID_PREFIX,

        "problem_text_md": problem_text_md,
        "ask_line_md": ask_line_md,

        "table_md": table_md,
        "full_table_md": full_table_md,

        "answer": sol["answer"],
        "answer_md": f"{sol['answer']}",
        "explanation_md": explanation_md,

        "meta": {
            "topic": "photoelectric_effect",
            "n": p.n, "m": p.m, "k": p.k,
            "A": p.A, "B": p.B, "C": p.C, "D": p.D,
            "truths": sol["truths"],
        }
    }


# ============================
#   문장 생성 (ㄴ, ㄷ)
#   → ★ 안정화 핵심: B=9일 때 빈 구간 방지 처리 포함
# ============================
def build_problem_payload(rng: random.Random, pid: str):
    p = generate_one(rng)

    # ---------------------------
    # ㄴ 선지 생성 (참/거짓 유지)
    # ---------------------------
    if p.n_truth:
        # 참: B ≥ y
        y = safe_randint(rng, 1, p.B)
        n_sentence = (
            f"P에 진동수가 {p.m}f₀인 빛을 비추면 방출되는 광전자의 최대 운동 에너지는 "
            f"{y}E₀ 이상이다."
        )
    else:
        # 거짓: B < y 이어야 함
        if p.B < 9:
            y = safe_randint(rng, p.B + 1, 9)
            n_sentence = (
                f"P에 진동수가 {p.m}f₀인 빛을 비추면 방출되는 광전자의 최대 운동 에너지는 "
                f"{y}E₀ 이상이다."
            )
        else:
            # ★ B=9이면 B+1..9는 불가능 → "미만" 형태로 false 직접 생성
            y = 1
            n_sentence = (
                f"P에 진동수가 {p.m}f₀인 빛을 비추면 방출되는 광전자의 최대 운동 에너지는 "
                f"{y}E₀ 미만이다."
            )

    # ---------------------------
    # ㄷ 선지 생성
    # ---------------------------
    if p.d_truth:
        d_sentence = f"①은 {p.D}E₀이다."
    else:
        wrong = [i for i in range(1, 10) if i != p.D]
        t = rng.choice(wrong)
        d_sentence = f"①은 {t}E₀이다."

    sol = solve(p, n_truth=p.n_truth, d_truth=p.d_truth)
    if not sol["is_unique"]:
        return None

    return to_problem_bank_payload(p, sol, pid, n_sentence, d_sentence)


# ============================
#   PACK 생성
# ============================
def make_pack(n_items=30, seed=1, out_path="HJHMPHYSICS1_photoelectric_pack.json"):
    rng = random.Random(seed)
    items = []
    tries = 0

    while len(items) < n_items:
        tries += 1
        if tries > 6000:
            raise RuntimeError("생성 실패: 조건 과도")

        pid = f"{ID_PREFIX}_{seed:04d}_{len(items)+1:03d}"
        payload = build_problem_payload(rng, pid)
        if payload is None:
            continue

        meta = payload["meta"]
        if not all(1 <= meta[x] <= 9 for x in ["A", "B", "C", "D"]):
            continue

        items.append(payload)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    return items


# ============================
#   MAIN
# ============================
if __name__ == "__main__":
    pack = make_pack(
        n_items=30,
        seed=18,
        out_path="HJHMPHYSICS1_photoelectric_pack.json"
    )
    print("Generated:", len(pack))
    print("Sample ID:", pack[0]["id"])
