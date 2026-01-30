# gene_detx_bank.py
# End-to-end:
# 1) generate candidate observed table (with shuffled ㉠~㉥ mapping, shuffled owners, changed sum cols, masking)
# 2) TRUE solver (no meta) enumerates mapping(720) x owner(30) and counts consistent global solutions
# 3) unique-answer check: answer option must be identical across ALL consistent solutions
# 4) export Problem Bank item fields + Pack JSON + MD

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Tuple, Iterable, Optional
import itertools, random, time, uuid, json, os

# =========================
# Constants
# =========================
ALLELES = ["A", "a", "B", "b", "D", "d"]
LOCI = [("A", "a"), ("B", "b"), ("D", "d")]
SYMS = ["㉠", "㉡", "㉢", "㉣", "㉤", "㉥"]
ROWS = ["(가)", "(나)", "(다)", "(라)", "(마)"]

CHOICES = [
    "① ㄱ",
    "② ㄴ",
    "③ ㄱ, ㄷ",
    "④ ㄴ, ㄷ",
    "⑤ ㄱ, ㄴ, ㄷ",
]


# =========================
# Bank Schema (your requested fields)
# =========================
@dataclass
class BankItem:
    id: str
    module: str
    id_prefix: str
    problem_text_md: str
    ask_line_md: str
    table_md: str
    full_table_md: str
    answer_md: str
    explanation_md: str
    meta: Dict[str, Any]


def new_id(id_prefix: str) -> str:
    return f"{id_prefix}{uuid.uuid4().hex[:10]}"


def pack_json(items: List[BankItem], pack_name: str, config: Dict[str, Any]) -> str:
    pack = {
        "pack_id": uuid.uuid4().hex,
        "pack_name": pack_name,
        "created_at": int(time.time()),
        "config": config,
        "count": len(items),
        "items": [asdict(x) for x in items],
    }
    return json.dumps(pack, ensure_ascii=False, indent=2)


# =========================
# Markdown render
# =========================
def parse_cells(table: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for row in table["cells"]:
        out[row["row"]] = row
    return out


def render_table_md(table: Dict[str, Any]) -> str:
    rows = table["rows"]
    syms = table["syms"]
    sum_cols = [c[0] for c in table["sum_cols"]]
    cells = parse_cells(table)

    header = ["세포"] + syms + sum_cols
    out = []
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + "|".join(["---"] * len(header)) + "|")
    for r in rows:
        row = [r]
        for s in syms:
            row.append(cells[r][s])
        for c in sum_cols:
            row.append(str(cells[r][c]))
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


# =========================
# Genetics (ground-truth generator, BUT solver will NOT use truth)
# =========================
def rand_genotype_for_locus(rng: random.Random, locus: Tuple[str, str]) -> Tuple[str, str]:
    x, y = locus
    t = rng.randint(0, 2)
    if t == 0:
        return (x, x)
    elif t == 1:
        return (x, y)
    else:
        return (y, y)


def rand_diploid_genotype(rng: random.Random) -> Dict[Tuple[str, str], Tuple[str, str]]:
    return {locus: rand_genotype_for_locus(rng, locus) for locus in LOCI}


def diploid_copy_counts(geno: Dict[Tuple[str, str], Tuple[str, str]]) -> Dict[str, int]:
    counts = {a: 0 for a in ALLELES}
    for locus in LOCI:
        a, b = geno[locus]
        if a == b:
            counts[a] += 2
        else:
            counts[a] += 1
            counts[b] += 1
    return counts


def make_gamete_from_genotype(rng: random.Random, geno: Dict[Tuple[str, str], Tuple[str, str]]) -> Dict[str, int]:
    counts = {a: 0 for a in ALLELES}
    for locus in LOCI:
        a, b = geno[locus]
        chosen = a if (a == b) else (a if rng.random() < 0.5 else b)
        counts[chosen] += 1
    return counts


def complementary_gamete(g1: Dict[str, int], geno: Dict[Tuple[str, str], Tuple[str, str]]) -> Dict[str, int]:
    g2 = {a: 0 for a in ALLELES}
    for locus in LOCI:
        x, y = locus
        a, b = geno[locus]
        if a == b:
            g2[a] += 1
        else:
            if g1[a] == 1:
                g2[b] += 1
            else:
                g2[a] += 1
    return g2


def child_genotype_from_gametes(gP: Dict[str, int], gQ: Dict[str, int]) -> Dict[Tuple[str, str], Tuple[str, str]]:
    geno = {}
    for locus in LOCI:
        x, y = locus
        p_allele = x if gP[x] == 1 else y
        q_allele = x if gQ[x] == 1 else y
        geno[locus] = (p_allele, q_allele)
    return geno


def genotype_to_str(geno: Dict[Tuple[str, str], Tuple[str, str]]) -> str:
    parts = []
    for locus in LOCI:
        a, b = geno[locus]
        pair = sorted([a, b], key=lambda z: (z.islower(), z))
        parts.append("".join(pair))
    return "".join(parts)


def pick_sum_rules(rng: random.Random, k: int = 2) -> List[Tuple[str, str, str]]:
    # choose k unordered allele pairs among 6
    all_pairs = []
    for i in range(6):
        for j in range(i + 1, 6):
            all_pairs.append((ALLELES[i], ALLELES[j]))
    rng.shuffle(all_pairs)
    rules = []
    for a1, a2 in all_pairs[:k]:
        rules.append((f"{a1}+{a2}", a1, a2))
    return rules


def mask_entries(rng: random.Random, sym_vals: Dict[str, str], mask_p: float) -> Dict[str, str]:
    out = dict(sym_vals)
    for k in out:
        if out[k] in ("○", "×") and rng.random() < mask_p:
            out[k] = "?"
    return out


# =========================
# TRUE solver (no meta): enumerate mapping x owner, check existence
# =========================
def all_symbol_mappings(syms: List[str]) -> Iterable[Dict[str, str]]:
    for perm in itertools.permutations(ALLELES, 6):
        yield {syms[i]: perm[i] for i in range(6)}


def all_owner_assignments(rows: List[str]) -> Iterable[Dict[str, str]]:
    idx = list(range(len(rows)))
    for P_idx in itertools.combinations(idx, 2):
        rem1 = [i for i in idx if i not in P_idx]
        for Q_idx in itertools.combinations(rem1, 2):
            rem2 = [i for i in rem1 if i not in Q_idx]
            R_idx = rem2[0]
            owner = {}
            for i in idx:
                if i in P_idx:
                    owner[rows[i]] = "P"
                elif i in Q_idx:
                    owner[rows[i]] = "Q"
                else:
                    owner[rows[i]] = "R"
            yield owner


def possible_ploidy_from_sums(row_cell: Dict[str, Any], sum_cols: List[Tuple[str, str, str]]) -> Tuple[bool, bool]:
    could_n, could_2n = True, True
    for col, _, _ in sum_cols:
        v = row_cell[col]
        if not (0 <= v <= 2):
            could_n = False
        if not (0 <= v <= 4):
            could_2n = False
    return could_n, could_2n


def enforce_locus_constraints(counts: Dict[str, int], ploidy: str) -> bool:
    target = 1 if ploidy == "n" else 2
    for x, y in LOCI:
        if counts[x] + counts[y] != target:
            return False
    return True


def row_counts_exist(
    row_cell: Dict[str, Any],
    mapping: Dict[str, str],
    ploidy: str,
    sum_cols: List[Tuple[str, str, str]],
    syms: List[str],
) -> Optional[Dict[str, int]]:
    # brute force per locus assignment (very small)
    if ploidy == "n":
        locus_options = []
        for x, y in LOCI:
            locus_options.append([{x: 1, y: 0}, {x: 0, y: 1}])
        for choice in itertools.product(*locus_options):
            counts = {a: 0 for a in ALLELES}
            for d in choice:
                for k, v in d.items():
                    counts[k] += v
            ok = True
            for sym in syms:
                obs = row_cell[sym]
                allele = mapping[sym]
                if obs == "○" and counts[allele] == 0:
                    ok = False
                    break
                if obs == "×" and counts[allele] != 0:
                    ok = False
                    break
            if not ok:
                continue
            for col, a1, a2 in sum_cols:
                if counts[a1] + counts[a2] != row_cell[col]:
                    ok = False
                    break
            if not ok:
                continue
            if enforce_locus_constraints(counts, "n"):
                return counts
        return None

    # 2n
    locus_options = []
    for x, y in LOCI:
        locus_options.append([{x: 2, y: 0}, {x: 0, y: 2}, {x: 1, y: 1}])
    for choice in itertools.product(*locus_options):
        counts = {a: 0 for a in ALLELES}
        for d in choice:
            for k, v in d.items():
                counts[k] += v
        ok = True
        for sym in syms:
            obs = row_cell[sym]
            allele = mapping[sym]
            if obs == "○" and counts[allele] == 0:
                ok = False
                break
            if obs == "×" and counts[allele] != 0:
                ok = False
                break
        if not ok:
            continue
        for col, a1, a2 in sum_cols:
            if counts[a1] + counts[a2] != row_cell[col]:
                ok = False
                break
        if not ok:
            continue
        if enforce_locus_constraints(counts, "2n"):
            return counts
    return None


def gametes_compatible_same_meiosis(g1: Dict[str, int], g2: Dict[str, int]) -> bool:
    # complement at every locus
    for x, y in LOCI:
        if g1[x] == 1 and g2[y] != 1:
            return False
        if g1[y] == 1 and g2[x] != 1:
            return False
    return True


def child_possible_from_PQ(P_g: Dict[str, int], Q_2n: Dict[str, int], R_2n: Dict[str, int]) -> bool:
    # enumerate possible Q gametes from Q_2n locus state
    def locus_state(q: Dict[str, int], x: str, y: str) -> str:
        if q[x] == 2:
            return "x"
        if q[y] == 2:
            return "y"
        return "h"

    choices = []
    for x, y in LOCI:
        st = locus_state(Q_2n, x, y)
        if st == "x":
            choices.append([{x: 1, y: 0}])
        elif st == "y":
            choices.append([{x: 0, y: 1}])
        else:
            choices.append([{x: 1, y: 0}, {x: 0, y: 1}])

    for prod in itertools.product(*choices):
        Qg = {a: 0 for a in ALLELES}
        for d in prod:
            for k, v in d.items():
                Qg[k] += v
        child = {a: P_g[a] + Qg[a] for a in ALLELES}
        if child == R_2n:
            return True
    return False


def option_index_from_truths(t1: bool, t2: bool, t3: bool) -> int:
    if t1 and (not t2) and (not t3):
        return 0
    if (not t1) and t2 and (not t3):
        return 1
    if t1 and (not t2) and t3:
        return 2
    if (not t1) and t2 and t3:
        return 3
    if t1 and t2 and t3:
        return 4
    return -1


def solve_count_solutions(table: Dict[str, Any]) -> Dict[str, Any]:
    rows = table["rows"]
    syms = table["syms"]
    sum_cols = table["sum_cols"]
    cells = parse_cells(table)
    stmts = table["statements"]

    answer_hist = [0, 0, 0, 0, 0]
    num_solutions = 0

    row_ploidy_possible = {r: possible_ploidy_from_sums(cells[r], sum_cols) for r in rows}

    locus_sets = [set(["A", "a"]), set(["B", "b"]), set(["D", "d"])]

    for mapping in all_symbol_mappings(syms):
        for owner in all_owner_assignments(rows):
            # ploidy quick feasibility
            ok = True
            for r in rows:
                could_n, could_2n = row_ploidy_possible[r]
                if owner[r] == "P" and not could_n:
                    ok = False
                    break
                if owner[r] in ("Q", "R") and not could_2n:
                    ok = False
                    break
            if not ok:
                continue

            # existence of counts per row
            row_counts = {}
            for r in rows:
                ploidy = "n" if owner[r] == "P" else "2n"
                cnt = row_counts_exist(cells[r], mapping, ploidy, sum_cols, syms)
                if cnt is None:
                    ok = False
                    break
                row_counts[r] = cnt
            if not ok:
                continue

            # P rows complementary
            P_rows = [r for r in rows if owner[r] == "P"]
            g1, g2 = row_counts[P_rows[0]], row_counts[P_rows[1]]
            if not gametes_compatible_same_meiosis(g1, g2):
                continue

            # child condition
            Q_rows = [r for r in rows if owner[r] == "Q"]
            R_row = [r for r in rows if owner[r] == "R"][0]
            Q_cnt = row_counts[Q_rows[0]]
            R_cnt = row_counts[R_row]
            if not (child_possible_from_PQ(g1, Q_cnt, R_cnt) or child_possible_from_PQ(g2, Q_cnt, R_cnt)):
                continue

            # valid global solution
            num_solutions += 1

            # statement truths under this solution
            sx, sy = stmts["stmt1_pair"]
            ax, ay = mapping[sx], mapping[sy]
            t1 = any(set([ax, ay]) == s for s in locus_sets)
            t2 = (owner[stmts["stmt2_row"]] == "Q")

            def locus_from_two_gametes(x: str, y: str) -> str:
                a = x if g1[x] == 1 else y
                b = x if g2[x] == 1 else y
                pair = sorted([a, b], key=lambda z: (z.islower(), z))
                return "".join(pair)

            P_geno = locus_from_two_gametes("A", "a") + locus_from_two_gametes("B", "b") + locus_from_two_gametes("D", "d")
            t3 = (P_geno == stmts["stmt3_P_geno"])

            opt = option_index_from_truths(t1, t2, t3)
            if 0 <= opt <= 4:
                answer_hist[opt] += 1

    return {"num_solutions": num_solutions, "answer_hist": answer_hist}


def unique_answer_from_solver_stats(stats: Dict[str, Any]) -> Tuple[bool, Optional[int]]:
    hist = stats["answer_hist"]
    total = sum(hist)
    if total == 0:
        return (False, None)
    nonzero = [i for i, v in enumerate(hist) if v > 0]
    if len(nonzero) == 1:
        return (True, nonzero[0])
    return (False, None)


# =========================
# Candidate generator (produces OBSERVED table only)
# =========================
def generate_candidate_table(seed: int, difficulty: int, sum_k: int = 2) -> Dict[str, Any]:
    rng = random.Random(seed)

    # ground truth genotypes (NOT used by solver)
    P = rand_diploid_genotype(rng)
    Q = rand_diploid_genotype(rng)

    gP1 = make_gamete_from_genotype(rng, P)
    gP2 = complementary_gamete(gP1, P)

    gQ = make_gamete_from_genotype(rng, Q)
    R = child_genotype_from_gametes(gP1, gQ)

    P_counts_2n = diploid_copy_counts(P)
    Q_counts_2n = diploid_copy_counts(Q)
    R_counts_2n = diploid_copy_counts(R)

    # owner shuffle (2 P gametes, 2 Q somatic, 1 R somatic)
    row_labels = ROWS[:]
    rng.shuffle(row_labels)
    P_rows = row_labels[:2]
    Q_rows = row_labels[2:4]
    R_row = row_labels[4]

    # symbol mapping shuffle
    alleles_shuffled = ALLELES[:]
    rng.shuffle(alleles_shuffled)
    symbol_to_allele_truth = {SYMS[i]: alleles_shuffled[i] for i in range(6)}
    # convert allele counts to symbol-space presence
    def presence_from_counts(counts: Dict[str, int]) -> Dict[str, str]:
        return {a: ("○" if counts[a] > 0 else "×") for a in ALLELES}

    sum_rules = pick_sum_rules(rng, k=sum_k)

    # masking
    mask_p = {1: 0.00, 2: 0.06, 3: 0.12, 4: 0.20, 5: 0.28}[int(difficulty)]

    cells = []
    for r in ROWS:
        if r in P_rows:
            gam = gP1 if r == P_rows[0] else gP2
            pres_allele = presence_from_counts(gam)
            counts = gam
        elif r in Q_rows:
            pres_allele = presence_from_counts(Q_counts_2n)
            counts = Q_counts_2n
        else:
            pres_allele = presence_from_counts(R_counts_2n)
            counts = R_counts_2n

        # map to symbols
        pres_sym = {}
        for sym in SYMS:
            allele = symbol_to_allele_truth[sym]
            pres_sym[sym] = pres_allele[allele]
        pres_sym = mask_entries(rng, pres_sym, mask_p)

        row_obj = {"row": r, **pres_sym}
        for col, a1, a2 in sum_rules:
            row_obj[col] = counts[a1] + counts[a2]
        cells.append(row_obj)

    # statements: random but controlled (some true/false)
    # stmt1: pick a random sym pair
    s_pair = tuple(rng.sample(SYMS, 2))
    # stmt2: pick a random row to claim Q
    stmt2_row = rng.choice(ROWS)
    # stmt3: claim P genotype (sometimes correct sometimes not)
    P_str = genotype_to_str(P)
    # make plausible wrong
    def wrong_P_str(s: str) -> str:
        chunks = [s[0:2], s[2:4], s[4:6]]
        k = rng.randrange(3)
        c = chunks[k]
        if c[0] != c[1]:
            chunks[k] = c[0] * 2
        else:
            x = c[0]
            if x in ("A", "a"):
                chunks[k] = "Aa"
            elif x in ("B", "b"):
                chunks[k] = "Bb"
            else:
                chunks[k] = "Dd"
        return "".join(chunks)

    stmt3 = P_str if rng.random() < 0.55 else wrong_P_str(P_str)

    return {
        "rows": ROWS[:],
        "syms": SYMS[:],
        "sum_cols": sum_rules,  # (col_name, allele1, allele2)
        "cells": cells,
        "statements": {
            "stmt1_pair": s_pair,
            "stmt2_row": stmt2_row,
            "stmt3_P_geno": stmt3,
        },
        # keep generator-only info if you want (NOT used by solver)
        "gen_hidden": {
            "seed": seed,
            "difficulty": difficulty,
            "mask_p": mask_p,
            "truth_symbol_to_allele": symbol_to_allele_truth,
            "truth_owner": {"P_rows": P_rows, "Q_rows": Q_rows, "R_row": R_row},
            "truth_P": P_str,
        },
    }


# =========================
# Build BankItem (uses TRUE solver stats only)
# =========================
def build_bank_item(module: str, id_prefix: str, table: Dict[str, Any], difficulty: int, seed: int) -> BankItem:
    stats = solve_count_solutions(table)
    ok, ans_idx = unique_answer_from_solver_stats(stats)
    if not ok or ans_idx is None:
        raise ValueError(f"NOT UNIQUE: {stats}")

    sum_cols_str = ", ".join([c[0] for c in table["sum_cols"]])

    problem_text_md = (
        "어떤 동물(2n)의 유전 형질 ㉮는 서로 다른 3개의 상염색체에 있는 3쌍의 대립유전자 "
        "A/a, B/b, D/d에 의해 결정된다.\n"
        f"표는 개체 P, Q, R의 세포 (가)~(마)에서 ㉠~㉥의 유무와 {sum_cols_str} 값을 나타낸 것이다.\n"
        "(가)~(마) 중 2개는 같은 G₁기 세포 I로부터 형성된 핵상 n인 P의 세포이고, 2개는 Q의 세포이며, 나머지 1개는 R의 세포이다.\n"
        "또한 P와 Q 사이에서 R7가 태어났다.\n"
        "(단, 돌연변이와 교차는 고려하지 않으며 A, a, B, b, D, d 각각의 1개당 DNA 상대량은 1이다.)\n"
        "\n(○: 있음, ×: 없음)"
    )

    s1x, s1y = table["statements"]["stmt1_pair"]
    s2row = table["statements"]["stmt2_row"]
    s3geno = table["statements"]["stmt3_P_geno"]

    ask_line_md = (
        "이에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?\n\n"
        "<보기>\n"
        f"ㄱ. {s1x}은 {s1y}과 대립유전자이다.\n"
        f"ㄴ. {s2row}는 Q의 세포이다.\n"
        f"ㄷ. P의 ㉮의 유전자형은 {s3geno}이다.\n\n"
        "① ㄱ ② ㄴ ③ ㄱ, ㄷ ④ ㄴ, ㄷ ⑤ ㄱ, ㄴ, ㄷ"
    )

    table_md = render_table_md(table)
    full_table_md = table_md  # (원하면 여기만 '예시 해'로 ? 채운 버전으로 확장 가능)

    answer_md = f"**정답:** {CHOICES[ans_idx]}"

    explanation_md = (
        f"- solver(메타 없이) 가능한 전체 해 수: **{stats['num_solutions']}**\n"
        f"- 옵션별 정답 분포(answer_hist): **{stats['answer_hist']}**\n"
        f"- 모든 해에서 정답이 **{CHOICES[ans_idx]}**로 동일 → **유일정답**"
    )

    return BankItem(
        id=new_id(id_prefix),
        module=module,
        id_prefix=id_prefix,
        problem_text_md=problem_text_md,
        ask_line_md=ask_line_md,
        table_md=table_md,
        full_table_md=full_table_md,
        answer_md=answer_md,
        explanation_md=explanation_md,
        meta={
            "seed": seed,
            "difficulty": difficulty,
            "solver": stats,
            "unique_answer": ans_idx,
            "sum_cols": table["sum_cols"],
            "statements": table["statements"],
            "gen_hidden": table.get("gen_hidden", {}),
        },
    )


# =========================
# Bank generation loop
# =========================
def generate_bank(
    n: int,
    module: str = "26GENEDETX",
    id_prefix: str = "26GENEDETX_",
    difficulty: int = 3,
    base_seed: int = 20260130,
    max_tries_per_item: int = 2000,
    sum_k: int = 2,
) -> List[BankItem]:
    bank: List[BankItem] = []
    seed = base_seed
    while len(bank) < n:
        made = False
        for _ in range(max_tries_per_item):
            t = generate_candidate_table(seed=seed, difficulty=difficulty, sum_k=sum_k)
            try:
                item = build_bank_item(module, id_prefix, t, difficulty, seed)
                bank.append(item)
                made = True
                seed += 1
                break
            except Exception:
                seed += 1
                continue
        if not made:
            raise RuntimeError("생성 실패: max_tries_per_item 증가 또는 마스킹/합열 규칙 완화 필요")
    return bank


def write_outputs(bank: List[BankItem], out_dir: str, pack_name: str, config: Dict[str, Any]) -> Tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    pack_str = pack_json(bank, pack_name=pack_name, config=config)
    json_path = os.path.join(out_dir, f"{pack_name}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(pack_str)

    md_path = os.path.join(out_dir, f"{pack_name}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        for i, item in enumerate(bank, 1):
            f.write(f"# {item.module} / {item.id}\n\n")
            f.write(item.problem_text_md + "\n\n")
            f.write(item.table_md + "\n\n")
            f.write(item.ask_line_md + "\n\n")
            f.write(item.answer_md + "\n\n")
            f.write("## 해설(내부)\n\n" + item.explanation_md + "\n\n")
            if i != len(bank):
                f.write("\n---\n\n")
    return json_path, md_path


# =========================
# CLI
# =========================
if __name__ == "__main__":
    # tweak here
    N = 30
    MODULE = "26GENEDETX"
    ID_PREFIX = "26GENEDETX_"
    DIFF = 3
    BASE_SEED = 20260130
    OUT_DIR = "./out"
    PACK_NAME = "26GENEDETX_pack_20260130"

    bank = generate_bank(
        n=N,
        module=MODULE,
        id_prefix=ID_PREFIX,
        difficulty=DIFF,
        base_seed=BASE_SEED,
        max_tries_per_item=4000,
        sum_k=2,
    )

    json_path, md_path = write_outputs(
        bank,
        out_dir=OUT_DIR,
        pack_name=PACK_NAME,
        config={"module": MODULE, "difficulty": DIFF, "n": N, "base_seed": BASE_SEED},
    )

    print("WROTE:")
    print(" -", json_path)
    print(" -", md_path)
