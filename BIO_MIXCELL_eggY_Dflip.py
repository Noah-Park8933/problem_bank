# BIO_MIXCELL_eggY_Dflip.py
# Row types fixed: P_somatic / Q_somatic / Q_egg / P_spermY
# D/d flip allowed with safety rules.
# Output: problem bank compatible JSON pack.

from __future__ import annotations
import json
import random
from dataclasses import dataclass
from datetime import datetime
from itertools import permutations
from typing import Dict, List, Tuple, Iterable, Optional, Set

ALLELES = ["A","a","B","b","D","d"]
AUTOSOMAL = ["A","a","B","b"]
XALLELES = ["D","d"]

ROWNAMES = ["I","II","III","IV"]

# ---------- (가) linked, no crossing: haplotypes & diplotypes ----------
HAPS = ["AB","Ab","aB","ab"]

def all_diplotypes() -> List[Tuple[str,str]]:
    out = []
    for i in range(len(HAPS)):
        for j in range(i, len(HAPS)):
            out.append((HAPS[i], HAPS[j]))
    return out  # 10

DIPLOS = all_diplotypes()

def hap_to_presence(h: str) -> Dict[str,bool]:
    return {
        "A": ("A" in h),
        "a": ("a" in h),
        "B": ("B" in h),
        "b": ("b" in h),
    }

def dip_to_presence(dip: Tuple[str,str]) -> Dict[str,bool]:
    p1 = hap_to_presence(dip[0])
    p2 = hap_to_presence(dip[1])
    return {k: (p1[k] or p2[k]) for k in AUTOSOMAL}

def dom_count_from_dip(dip: Tuple[str,str]) -> int:
    Acount = (1 if "A" in dip[0] else 0) + (1 if "A" in dip[1] else 0)
    Bcount = (1 if "B" in dip[0] else 0) + (1 if "B" in dip[1] else 0)
    return Acount + Bcount  # 0..4

# ---------- (나) X-linked ----------
# P: male X allele either 'D' or 'd'
# Q: female genotype 'DD','Dd','dd'
def female_X_presence(g: str) -> Dict[str,bool]:
    return {"D": ("D" in g), "d": ("d" in g)}

def male_X_presence(x: str) -> Dict[str,bool]:
    return {"D": (x=="D"), "d": (x=="d")}

# ---------- row types (fixed set) ----------
ROW_TYPES = ["P_somatic", "Q_somatic", "Q_egg", "P_spermY"]
PLOIDY = {"P_somatic":"2n", "Q_somatic":"2n", "Q_egg":"n", "P_spermY":"n"}

@dataclass(frozen=True)
class World:
    P_ga: Tuple[str,str]
    Q_ga: Tuple[str,str]
    P_X: str        # 'D' or 'd'
    Q_X: str        # 'DD','Dd','dd'

def iter_worlds() -> Iterable[World]:
    for P_ga in DIPLOS:
        for Q_ga in DIPLOS:
            for P_X in ["D","d"]:
                for Q_X in ["DD","Dd","dd"]:
                    yield World(P_ga=P_ga, Q_ga=Q_ga, P_X=P_X, Q_X=Q_X)

Presence = Dict[str,bool]

def dedupe_patterns(pats: List[Presence]) -> List[Presence]:
    uniq = []
    seen = set()
    for p in pats:
        key = tuple(int(p[a]) for a in ALLELES)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq

def q_egg_X_alleles(qX: str) -> List[str]:
    if qX == "DD":
        return ["D"]
    if qX == "Dd":
        return ["D","d"]
    return ["d"]  # dd

def patterns_for(world: World, rowtype: str) -> List[Presence]:
    if rowtype == "P_somatic":
        auto = dip_to_presence(world.P_ga)
        x = male_X_presence(world.P_X)
        return [{**auto, **x}]

    if rowtype == "Q_somatic":
        auto = dip_to_presence(world.Q_ga)
        x = female_X_presence(world.Q_X)
        return [{**auto, **x}]

    if rowtype == "Q_egg":
        pres_list: List[Presence] = []
        xs = q_egg_X_alleles(world.Q_X)
        for h in world.Q_ga:  # one haplotype from Q
            auto = hap_to_presence(h)
            for x in xs:
                pres_list.append({**auto, **male_X_presence(x)})  # egg carries one X allele
        return dedupe_patterns(pres_list)

    if rowtype == "P_spermY":
        pres_list: List[Presence] = []
        for h in world.P_ga:
            auto = hap_to_presence(h)
            x = {"D": False, "d": False}  # anchor
            pres_list.append({**auto, **x})
        return dedupe_patterns(pres_list)

    raise ValueError(rowtype)

# ---------- observed constraints ----------
# obs: 'O'(present) / 'X'(absent) / '?'(unknown)
def consistent_cell(obs: str, present: bool) -> bool:
    if obs == "?":
        return True
    if obs == "O":
        return present
    if obs == "X":
        return (not present)
    raise ValueError(obs)

def pattern_consistent_with_row(obs_row: Dict[str,str], pres: Presence) -> bool:
    return all(consistent_cell(obs_row[a], pres[a]) for a in ALLELES)

def compatible_patterns(obs_row: Dict[str,str], pres_set: List[Presence]) -> List[Presence]:
    return [p for p in pres_set if pattern_consistent_with_row(obs_row, p)]

@dataclass
class SolutionFamily:
    world: World
    layout: Tuple[str,str,str,str]              # rowtypes for I..IV
    row_patterns: Dict[int, List[Presence]]     # row index -> compatible pres patterns

def solve_families(obs_table_4x6: List[List[str]], max_families: int = 20000) -> List[SolutionFamily]:
    obs_rows = []
    for r in range(4):
        obs_rows.append({ALLELES[c]: obs_table_4x6[r][c] for c in range(6)})

    layouts = list(permutations(ROW_TYPES, 4))  # 24
    fams: List[SolutionFamily] = []
    for w in iter_worlds():
        for lay in layouts:
            row_patterns: Dict[int, List[Presence]] = {}
            ok = True
            for ri in range(4):
                rowtype = lay[ri]
                pres_set = patterns_for(w, rowtype)
                comp = compatible_patterns(obs_rows[ri], pres_set)
                if not comp:
                    ok = False
                    break
                row_patterns[ri] = comp
            if ok:
                fams.append(SolutionFamily(world=w, layout=lay, row_patterns=row_patterns))
                if len(fams) >= max_families:
                    return fams
    return fams

# ---------- statement evaluation (ㄱㄴㄷ) ----------
# Statement set can be swapped later.
def stmt_g(fam: SolutionFamily) -> Tuple[bool,bool]:
    # ㄱ: "I은 Q에서 나온 세포이다." -> I row is either Q_somatic or Q_egg
    is_q = fam.layout[0] in ("Q_somatic", "Q_egg")
    return (is_q, is_q)

def stmt_n(fam: SolutionFamily) -> Tuple[bool,bool]:
    # ㄴ: "III은 B와 b를 모두 가진다."
    pats = fam.row_patterns[2]
    def holds(p: Presence) -> bool:
        return p["B"] and p["b"]
    vals = [holds(p) for p in pats]
    return (min(vals), max(vals))

def stmt_d(fam: SolutionFamily) -> Tuple[bool,bool]:
    # ㄷ: "II와 IV의 핵상이 같다."
    p2 = PLOIDY[fam.layout[1]]
    p4 = PLOIDY[fam.layout[3]]
    val = (p2 == p4)
    return (val, val)

def aggregate_stmt(fams: List[SolutionFamily], per_fam_fn) -> str:
    # 'T' / 'F' / 'V' (varies)
    if not fams:
        return "NONE"
    min_all = True
    max_all = False
    for fam in fams:
        mn, mx = per_fam_fn(fam)
        min_all = min_all and mn
        max_all = max_all or mx
    if min_all and max_all:
        return "T"
    if (not min_all) and (not max_all):
        return "F"
    return "V"

# Options mapping (edit if needed)
# ① ㄱ, ② ㄴ, ③ ㄷ, ④ ㄱㄴ, ⑤ ㄱㄷ
def option_from_truth(truths: Tuple[bool,bool,bool]) -> Optional[int]:
    g, n, d = truths
    if g and (not n) and (not d): return 1
    if (not g) and n and (not d): return 2
    if (not g) and (not n) and d: return 3
    if g and n and (not d): return 4
    if g and (not n) and d: return 5
    return None

def invariant_sum_k(fams: List[SolutionFamily]) -> Optional[int]:
    vals: Set[int] = set()
    for fam in fams:
        k = dom_count_from_dip(fam.world.P_ga) + dom_count_from_dip(fam.world.Q_ga)
        vals.add(k)
        if len(vals) > 1:
            return None
    return next(iter(vals)) if vals else None

# ---------- base table + mutations ----------
def presence_to_OX(p: Presence, allele: str) -> str:
    return "O" if p[allele] else "X"

def build_base_table(world: World, layout: Tuple[str,str,str,str], rng: random.Random) -> List[List[str]]:
    table = []
    for ri in range(4):
        rowtype = layout[ri]
        pats = patterns_for(world, rowtype)
        p = rng.choice(pats)  # choose a concrete gamete option if needed
        table.append([presence_to_OX(p, a) for a in ALLELES])

    # enforce Y-sperm anchor
    for ri in range(4):
        if layout[ri] == "P_spermY":
            table[ri][ALLELES.index("D")] = "X"
            table[ri][ALLELES.index("d")] = "X"
    return table

def _rowtype_has_X(rowtype: str) -> bool:
    # must have at least one of D/d present:
    # P_spermY: no X (special)
    return rowtype != "P_spermY"

def allowed_flip_cell(table: List[List[str]], layout: Tuple[str,str,str,str], r: int, c: int) -> bool:
    allele = ALLELES[c]
    rowtype = layout[r]

    # never flip D/d in Y-sperm
    if rowtype == "P_spermY" and allele in XALLELES:
        return False

    # if flipping D/d, ensure row still has at least one X-allele present after flip (except Y-sperm)
    if allele in XALLELES and _rowtype_has_X(rowtype):
        d_idx = ALLELES.index("D")
        dd_idx = ALLELES.index("d")
        curD = table[r][d_idx]
        curd = table[r][dd_idx]
        new_self = "O" if table[r][c] == "X" else "X"
        other = curd if allele == "D" else curD
        # if both become X -> X chromosome vanishes -> reject
        if new_self == "X" and other == "X":
            return False

    return True

def flip_cells(table: List[List[str]], layout: Tuple[str,str,str,str], rng: random.Random, flips: int) -> List[List[str]]:
    out = [row[:] for row in table]

    candidates: List[Tuple[int,int]] = []
    for r in range(4):
        for c in range(6):
            # skip if not allowed
            if not allowed_flip_cell(out, layout, r, c):
                continue
            candidates.append((r,c))

    rng.shuffle(candidates)
    chosen = []
    for (r,c) in candidates:
        if len(chosen) >= flips:
            break
        # re-check on current out (since flips change row constraints)
        if allowed_flip_cell(out, layout, r, c):
            chosen.append((r,c))
            out[r][c] = "O" if out[r][c] == "X" else "X"

    if len(chosen) < flips:
        # failed to find enough safe flips; return original to be rejected by validator later
        return table

    # re-enforce Y-sperm anchor
    for ri in range(4):
        if layout[ri] == "P_spermY":
            out[ri][ALLELES.index("D")] = "X"
            out[ri][ALLELES.index("d")] = "X"

    return out

def mask_cells(table: List[List[str]], layout: Tuple[str,str,str,str], rng: random.Random, qcount: int) -> List[List[str]]:
    out = [row[:] for row in table]
    # keep Y-sperm anchor visible
    candidates: List[Tuple[int,int]] = []
    for r in range(4):
        for c, a in enumerate(ALLELES):
            if layout[r] == "P_spermY" and a in XALLELES:
                continue
            candidates.append((r,c))
    rng.shuffle(candidates)
    for (r,c) in candidates[:qcount]:
        out[r][c] = "?"
    return out

# ---------- item generation ----------
def make_item(rng: random.Random, max_attempts: int = 4000) -> Optional[Dict]:
    layouts = list(permutations(ROW_TYPES, 4))  # 24
    worlds = list(iter_worlds())                # 600
    rng.shuffle(worlds)

    for _ in range(max_attempts):
        w = rng.choice(worlds)
        lay = rng.choice(layouts)

        base = build_base_table(w, lay, rng)

        flips = rng.choice([1,2,3])
        flipped = flip_cells(base, lay, rng, flips=flips)
        if flipped == base:
            continue

        qcount = rng.choice([8,9,10])
        obs = mask_cells(flipped, lay, rng, qcount=qcount)

        fams = solve_families(obs, max_families=20000)
        if not fams:
            continue

        g_stat = aggregate_stmt(fams, stmt_g)
        n_stat = aggregate_stmt(fams, stmt_n)
        d_stat = aggregate_stmt(fams, stmt_d)

        if "V" in (g_stat, n_stat, d_stat):
            continue

        truths = (g_stat=="T", n_stat=="T", d_stat=="T")
        ans = option_from_truth(truths)
        if ans is None:
            continue

        k = invariant_sum_k(fams)

        cond_line = ""
        if k is not None:
            cond_line = f"또한 P의 ①과 Q의 ①의 합은 {k}이다. (①은 (가) 표현형 값)\n"

        problem_text = (
            "어떤 동물(2n)에서 (가)는 5번 염색체에 있는 A/a, B/b 두 쌍의 대립유전자에 의해 결정되며, "
            "한 개체의 (가) 표현형 값 ①은 그 개체의 유전자형에서 대문자 대립유전자(A, B)의 총 개수이다.\n"
            "(나)는 X 염색체의 D/d에 의해 결정되며 D가 d에 대해 우성이다.\n"
            "표는 P(수컷)과 Q(암컷)에서 얻은 서로 다른 4개의 세포(I~IV)에 존재하는 대립유전자를 나타낸 것이다.\n"
            + cond_line +
            "다음 <보기>에서 옳은 것만을 있는 대로 고른 것은? (단, 교차와 돌연변이는 고려하지 않는다.)"
        )

        grid = [["세포","A","a","B","b","D","d"]]
        for i, rn in enumerate(ROWNAMES):
            grid.append([rn] + obs[i])

        choices = ["ㄱ", "ㄴ", "ㄷ", "ㄱ, ㄴ", "ㄱ, ㄷ"]

        sol = (
            "표를 만족하는 가능한 모든 경우(부모 유전자형, 행 배치, 생식세포 선택)를 고려하여 <보기>를 판정한다.\n"
            f"- ㄱ: {g_stat}\n"
            f"- ㄴ: {n_stat}\n"
            f"- ㄷ: {d_stat}\n"
            f"따라서 정답은 {ans}번이다.\n"
            f"(참고) flips={flips}, ?={qcount}, families={len(fams)}"
        )

        payload = {
            "table_grid": grid,
            "table": grid,
            "obs_table_4x6": obs,
            "problem_text_md": problem_text,
            "ask_line_md": "정답을 고르시오.",
            "choices": choices,
            "answer": ans,
            "answer_text_md": str(ans),
            "solution_md": sol,
            "meta": {
                "row_types_used": list(lay),
                "flips": flips,
                "qcount": qcount,
                "k_sum": k,
            }
        }

        pid = f"BIO_MIXCELL_{rng.randrange(16**10):010x}"
        return {
            "id": pid,
            "module": "BIO_MIXCELL",
            "id_prefix": "BIO_MIXCELL_",
            "difficulty": 3,
            "problem_text_md": problem_text,
            "ask_line_md": "정답을 고르시오.",
            "answer_text_md": str(ans),
            "solution_md": sol,
            "payload": payload,
        }

    return None

def generate_pack(n: int, seed: int, out_path: str) -> Dict:
    rng = random.Random(seed)
    items = []
    guard = 0
    while len(items) < n and guard < 40000:
        guard += 1
        it = make_item(rng, max_attempts=4000)
        if it is None:
            continue
        items.append(it)

    pack = {
        "pack_id": f"BIO_MIXCELL_pack_{seed}",
        "pack_name": f"BIO_MIXCELL_pack_{seed}",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "module": "250515_PGD_",
            "difficulty": 3,
            "n": n,
            "base_seed": seed,
        },
        "count": len(items),
        "items": items,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)
    return pack

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260201)
    ap.add_argument("--out", type=str, default="BIO_MIXCELL_pack.json")
    args = ap.parse_args()

    pack = generate_pack(n=args.n, seed=args.seed, out_path=args.out)
    print(f"saved: {args.out} (items={pack['count']})")

if __name__ == "__main__":
    main()
