# division_pack/main.py
from __future__ import annotations

import argparse
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from .config import DEFAULT_N, DEFAULT_MAX_TRIES_PER_PROBLEM, BLANK_RANGE, MIN_KNOWN_PER_ROW, FEMALE_X_N1_SUM2, CELL_LABELS
from .simulate import make_truth, build_person_three_rows, shuffle_cell_labels
from .mask import mask_table
from .solver import count_answer_solutions
from .export import save_pack
from .config import ALLELES
MODULE_CODE = "division"
ID_PREFIX = "DIV_"
def masked_table_to_md(masked: Dict[str, Dict[str, Any]], cell_labels: List[str]) -> str:
    cols = ["E", "e", "F", "f", "G", "g"]
    lines = []
    lines.append("|세포| " + " | ".join(cols) + " |")
    lines.append("|---|" + "|".join(["---"] * len(cols)) + "|")
    for c in cell_labels:
        row = [str(masked[c][k]) for k in cols]
        lines.append("|" + c + "| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"
def construct_mask_unique(
    rng: random.Random,
    full: Dict[str, Dict[str, int]],
    target_blanks: int,
    min_known_per_row: int,
) -> Tuple[Dict[str, Dict[str, Any]] | None, int, List[Dict[str, Any]] | None]:
    """
    full -> masked 를 '구성'한다.
    - ?를 하나씩 추가해보며
    - solver 해가 1개면 확정
    - 1개가 아니면 롤백
    규칙:
    - 같은 row에서 같은 locus(E/e)를 둘 다 ?로 금지
    - row당 최소 공개칸 유지
    """
    masked: Dict[str, Dict[str, Any]] = {c: dict(full[c]) for c in CELL_LABELS}

    row_blank = {c: 0 for c in CELL_LABELS}
    masked_locus_in_row = {c: set() for c in CELL_LABELS}

    # 후보 좌표(랜덤 순서)
    coords = [(c, a) for c in CELL_LABELS for a in ALLELES]
    rng.shuffle(coords)

    # 진행이 막힐 때 재섞기용 카운터
    rollback_count = 0
    i = 0

    while sum(row_blank.values()) < target_blanks:
        if i >= len(coords):
            # 더 이상 시도할 칸이 없음 -> 실패
            return None, 0, None

        c, a = coords[i]
        i += 1

        if masked[c][a] == "?":
            continue

        known_now = len(ALLELES) - row_blank[c]
        if known_now <= min_known_per_row:
            continue

        locus = a.upper()
        if locus in masked_locus_in_row[c]:
            continue

        # 시도
        prev = masked[c][a]
        masked[c][a] = "?"
        masked_locus_in_row[c].add(locus)
        row_blank[c] += 1

        sols = count_answer_solutions(masked)
        if len(sols) == 1:
            # 성공: 그대로 유지
            continue

        # 실패: 롤백
        masked[c][a] = prev
        masked_locus_in_row[c].remove(locus)
        row_blank[c] -= 1
        rollback_count += 1

        # 너무 막히면 후보 재구성(아직 ? 아닌 칸만)
        if rollback_count % 120 == 0:
            coords = [(cc, aa) for cc in CELL_LABELS for aa in ALLELES if masked[cc][aa] != "?"]
            rng.shuffle(coords)
            i = 0

    sols_final = count_answer_solutions(masked)
    if len(sols_final) != 1:
        return None, 0, None

    blanks = sum(row_blank.values())
    return masked, blanks, sols_final

def kst_now_iso() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).isoformat(timespec="seconds")
def generate_one_problem(rng: random.Random, pid: int) -> Dict[str, Any]:
    # truth를 몇 번 바꿔가며 "목표 blank를 만족하는" masked를 구성
    for _ in range(500):
        truth = make_truth(rng)

        p1_rows = build_person_three_rows(truth, truth.p1)
        p2_rows = build_person_three_rows(truth, truth.p2)

        full, owner = shuffle_cell_labels(rng, p1_rows, p2_rows)

        target_blanks = rng.randint(BLANK_RANGE[0], BLANK_RANGE[1])

        masked, blanks, sols = construct_mask_unique(
            rng=rng,
            full=full,
            target_blanks=target_blanks,
            min_known_per_row=MIN_KNOWN_PER_ROW,
        )
        if masked is None:
            continue

        first_sol = sols[0]

        # 문제은행용 pid (예: DIV_0001)
        bank_pid = f"{ID_PREFIX}{pid:04d}"
        table_md = masked_table_to_md(masked, CELL_LABELS)  # ✅ 여기!

        return {
            "pid": bank_pid,  # ✅ 파서가 pid/id/problem_id 등을 찾음
            "payload": {
                # ✅ normalize_tables가 최상위에서 찾는 키들
                "masked_table": masked,
                "full_table": full,
            "problem_text_md": (
                "### Division (Constructive)\n"
                "- 다음은 감수분열 과정에서 관찰된 6개 세포(가~바)의 대립유전자이다.\n"
                "- 각 세포는 두 사람(P1, P2) 중 한 사람에게서 얻어진 것이며, 각 사람에 대해 3개 세포가 있다. 단, P1은 남자, P2는 여자이다.\n\n"
                + table_md
            ), 
             "ask_line_md": "표의 물음표(?)를 모두 채우고 세포의 주인을 찾으시오.",

                # 있으면 편한 부가정보(문제은행에서 같이 저장됨)
                "cell_labels": CELL_LABELS,
                "owner": owner,
                "sex": {"P1": "M", "P2": "F"},
                "locus_positions": truth.pos,
                "text": (
                    "다음은 감수분열 과정에서 관찰된 6개 세포(가~바)의 대립유전자 개수이다.\n"
                    "각 세포는 두 사람(P1, P2) 중 한 사람에게서 얻어진 것이며, 각 사람에 대해 3개 세포가 있다.\n"
                    "표의 물음표(?)는 가려진 값이다.\n"
                    "P1은 남자, P2는 여자이다.\n"
                    "가능한 (사람 분할, X좌위치) 조합이 유일하도록 할 때, 표를 해석하라."
                ),

                "rules": {
                    "x_loci_count": len(truth.x_loci),
                    "x_loci": truth.x_loci,
                    "linked_on_x": False,
                    "blank_range": list(BLANK_RANGE),
                    "min_known_per_row": MIN_KNOWN_PER_ROW,
                    "female_x_n1_sum2": FEMALE_X_N1_SUM2,
                    "sex_fixed": {"P1": "M", "P2": "F"},
                },
                "proof": {
                    "num_solutions": 1,
                    "first_solution": first_sol,
                    "blanks": blanks,
                },
            },
        }

    raise RuntimeError("generate_one_problem: couldn't construct unique-solution masked table")
def _worker_make_one(args):
    """
    프로세스 워커 1개가 문제 1개를 완성해서 dict로 반환.
    args: (pid, seed)
    """
    pid, seed = args
    # 각 pid마다 독립 RNG
    rng = random.Random(seed)
    return generate_one_problem(rng, pid)


def generate_pack_parallel(n: int, seed: int, max_tries_per_problem: int, workers: int) -> Dict[str, Any]:
    """
    n개 문제를 병렬로 생성.
    - pid별로 seed를 파생시켜 재현성 유지
    - 각 워커는 generate_one_problem 내부에서 유일정답 될 때까지 탐색
    """
    # pid별 seed 파생(충돌 방지)
    job_args = []
    for pid in range(1, n + 1):
        # 간단한 seed 믹싱(재현성 OK)
        job_seed = (seed * 1000003) ^ (pid * 10007) ^ 0x9E3779B9
        job_args.append((pid, job_seed))

    problems: List[Dict[str, Any]] = [None] * n

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_worker_make_one, a): a[0] for a in job_args}

        for fut in as_completed(futures):
            pid = futures[fut]
            p = fut.result()  # 여기서 워커 에러도 그대로 뜸
            problems[pid - 1] = p

    return {
        "module_code": MODULE_CODE,
        "id_prefix": ID_PREFIX,
        "meta": {
            "version": "division-pack-v1",
            "created_at": kst_now_iso(),
            "seed": seed,
            "n": n,
            "note": f"Parallel generation with workers={workers}. Kept only problems with exactly 1 solution.",
        },
        "problems": problems,
    }

def generate_pack(n: int, seed: int, max_tries_per_problem: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    problems: List[Dict[str, Any]] = []

    for pid in range(1, n + 1):
        for _ in range(max_tries_per_problem):
            p = generate_one_problem(rng, pid)
            if p["proof"]["num_solutions"] == 1:
                problems.append(p)
                break
        else:
            raise RuntimeError(f"Problem {pid} failed after {max_tries_per_problem} tries (couldn't find unique-solution case).")

    return {
        "meta": {
            "version": "division-pack-v1",
            "created_at": kst_now_iso(),
            "seed": seed,
            "n": n,
            "note": "Only problems with exactly 1 solution under (partition, sex, X-loci) were kept.",
        },
        "problems": problems,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--module_code", type=str, default="division")
    ap.add_argument("--id_prefix", type=str, default="DIV_")
    ap.add_argument("--n", type=int, default=DEFAULT_N)
    ap.add_argument("--out", type=str, default="pack.json")
    ap.add_argument("--seed", type=int, default=20260129)
    ap.add_argument("--workers", type=int, default=0)  # 0이면 자동
    ap.add_argument("--max_tries", type=int, default=DEFAULT_MAX_TRIES_PER_PROBLEM)
    args = ap.parse_args()
    global MODULE_CODE, ID_PREFIX
    MODULE_CODE = args.module_code
    ID_PREFIX = args.id_prefix
    if args.workers <= 0:
        workers = max(1, (os.cpu_count() or 2) - 1)  # 기본: 코어-1
    else:
        workers = args.workers

    # 병렬 사용
    pack = generate_pack_parallel(args.n, args.seed, args.max_tries, workers)
    save_pack(pack, args.out)

    print(f"✅ saved: {args.out}")
    print(f"meta: version={pack['meta']['version']} seed={pack['meta']['seed']} n={pack['meta']['n']}")

if __name__ == "__main__":
    main()
