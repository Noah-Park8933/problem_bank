# xlinked_ABD_bank.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Tuple, Optional
import itertools, random, time, uuid, json, os

# =========================================
# Bank schema
# =========================================
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

# 보기 선택지(원문)
CHOICES = ["① ㄱ", "② ㄴ", "③ ㄱ, ㄷ", "④ ㄴ, ㄷ", "⑤ ㄱ, ㄴ, ㄷ"]

# =========================================
# Problem text template (same as image)
# =========================================
def base_problem_text() -> str:
    return (
        "16. 사람의 유전 형질 (가)는 1쌍의 대립유전자 A와 a에 의해, (나)는 2쌍의 대립유전자 B와 b, D와 d에 의해 결정된다. "
        "(가)의 유전자는 상염색체에, (나)의 유전자는 X 염색체에 있다. "
        "표 (가)는 남자 P와 여자 Q의 세포 I～IV에서 A, B, D의 유무를, "
        "(나)는 P와 Q 사이에서 태어난 자녀 1, 자녀 2, Q의 성별과 체세포 1개당 b와 d의 DNA 상대량을 나타낸 것이다. "
        "I～IV 중 2개는 P의 세포이고 나머지 2개는 Q의 세포이다. "
        "I～IV 중 2개는 핵상이 2n이고 나머지 2개는 핵상이 n이다.\n"
        "(단, 돌연변이와 교차는 고려하지 않으며, A, a, B, b, D, d 각각의 1개당 DNA 상대량은 1이다.) [3점]"
    )

# =========================================
# Genetics model
# (가): autosomal A/a
# (나): X-linked haplotype over (B,D) with NO crossover
# =========================================
AUTOG = ["AA", "Aa", "aa"]
XHAPS = ["BD", "Bd", "bD", "bd"]  # one X carries one of each locus allele

def gamete_from_A(geno: str, pick: int) -> str:
    if geno == "AA": return "A"
    if geno == "aa": return "a"
    return "A" if pick == 0 else "a"  # Aa

def geno_has_A(geno: str) -> bool:
    return "A" in geno

def count_allele_in_female(h1: str, h2: str, allele: str) -> int:
    return int(allele in h1) + int(allele in h2)

def child_bd_counts(momX: Tuple[str,str], dadX: str, sex: str, mom_pick: str) -> Tuple[int,int]:
    """Return (b_count, d_count) in somatic cell for child."""
    mh = momX[0] if mom_pick == "X1" else momX[1]
    if sex == "M":
        return (int("b" in mh), int("d" in mh))
    # F
    return (int("b" in mh) + int("b" in dadX),
            int("d" in mh) + int("d" in dadX))

# =========================================
# Cell table (가): presence/absence of A, B, D
# We encode symbols: "O"(○), "X"(×), "?" , "a"(ⓐ)
# =========================================
GENES_G = ["A","B","D"]
CELLS = ["I","II","III","IV"]

def presence_symbol(present: bool) -> str:
    return "O" if present else "X"

def render_table_g_md(obs_g: Dict[str, Dict[str,str]]) -> str:
    # 표(가)만 "순수 표"로 출력
    header = ["세포", "A", "B", "D"]
    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"]*len(header)) + " |")

    def sym(x: str) -> str:
        if x == "O": return "○"
        if x == "X": return "×"
        if x == "?": return "?"
        if x == "a": return "ⓐ"
        return x

    for c in CELLS:
        row = [c, sym(obs_g[c]["A"]), sym(obs_g[c]["B"]), sym(obs_g[c]["D"])]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)

def render_table_n_md(sex_Q: str, q_b: int, q_d: Optional[int],
                      c1_sex: str, c1_b: int, c1_d: int,
                      c2_sex: str, c2_b: int, c2_d: int) -> str:
    lines = []
    lines.append("| 구분 | 성별 | b | d |")
    lines.append("| --- | --- | ---: | ---: |")
    lines.append(f"| Q | {sex_Q} | {q_b} | {('?' if q_d is None else q_d)} |")
    lines.append(f"| 자녀1 | {c1_sex} | {c1_b} | {c1_d} |")
    lines.append(f"| 자녀2 | {c2_sex} | {c2_b} | {c2_d} |")
    return "\n".join(lines)

def render_table_n_md(sex_Q: str, q_b: int, q_d: Optional[int], c1_sex: str, c1_b: int, c1_d: int, c2_sex: str, c2_b: int, c2_d: int) -> str:
    # 표 (나)
    out = []
    out.append("**(나)**")
    out.append("")
    out.append("| 구분 | 성별 | b | d |")
    out.append("|---|---|---:|---:|")
    out.append(f"| Q | {sex_Q} | {q_b} | {('?' if q_d is None else q_d)} |")
    out.append(f"| 자녀1 | {c1_sex} | {c1_b} | {c1_d} |")
    out.append(f"| 자녀2 | {c2_sex} | {c2_b} | {c2_d} |")
    return "\n".join(out)

# =========================================
# “True solver” (no meta): brute force
# We collect invariants needed for ㄱㄴㄷ
# =========================================
def option_index(t1: bool, t2: bool, t3: bool) -> int:
    """
    options:
      ① ㄱ
      ② ㄴ
      ③ ㄱ, ㄷ
      ④ ㄴ, ㄷ
      ⑤ ㄱ, ㄴ, ㄷ
    """
    if t1 and (not t2) and (not t3): return 0
    if (not t1) and t2 and (not t3): return 1
    if t1 and (not t2) and t3: return 2
    if (not t1) and t2 and t3: return 3
    if t1 and t2 and t3: return 4
    return -1

def match_symbol(exp: bool, obs: str, a_value: Optional[bool]) -> Tuple[bool, Optional[bool]]:
    if obs == "?":
        return True, a_value
    if obs == "O":
        return (exp is True), a_value
    if obs == "X":
        return (exp is False), a_value
    if obs == "a":  # ⓐ
        if a_value is None:
            return True, exp
        return (a_value == exp), a_value
    raise ValueError(obs)

def expected_presence_cell(
    owner: str, ploidy: str,
    male_n_type: Optional[str],
    female_pickX: Optional[str],
    female_pickA: Optional[int],
    male_pickA: Optional[int],
    dadA: str, momA: str,
    dadX: str, momX: Tuple[str,str],
) -> Dict[str,bool]:
    # A presence
    if ploidy == "2n":
        A_present = geno_has_A(dadA) if owner == "P" else geno_has_A(momA)
    else:
        if owner == "P":
            if male_pickA is None:
                raise RuntimeError("male n A pick missing")
            A_present = (gamete_from_A(dadA, male_pickA) == "A")
        else:
            if female_pickA is None:
                raise RuntimeError("female n A pick missing")
            A_present = (gamete_from_A(momA, female_pickA) == "A")

    # B,D presence (X-linked)
    if ploidy == "2n":
        if owner == "P":
            B_present = ("B" in dadX); D_present = ("D" in dadX)
        else:
            B_present = ("B" in momX[0]) or ("B" in momX[1])
            D_present = ("D" in momX[0]) or ("D" in momX[1])
    else:
        if owner == "P":
            if male_n_type is None:
                raise RuntimeError("male n type missing")
            if male_n_type == "Y":
                B_present = False; D_present = False
            else:
                B_present = ("B" in dadX); D_present = ("D" in dadX)
        else:
            if female_pickX is None:
                raise RuntimeError("female n pickX missing")
            hx = momX[0] if female_pickX == "X1" else momX[1]
            B_present = ("B" in hx); D_present = ("D" in hx)

    return {"A": A_present, "B": B_present, "D": D_present}

def solve_collect_invariants(
    obs_g: Dict[str, Dict[str,str]],
    q_d_obs: Optional[int],  # None if '?'
    c1: Tuple[str,int,int],  # (sex, b, d)
    c2: Tuple[str,int,int],
) -> Dict[str,Any]:
    """
    Return:
      - num_solutions
      - a_values (set of bool for ⓐ)
      - III_is_P values
      - Q_is_BbDd values  (means momX == {Bd, bD})
    """
    sols = 0
    a_set = set()
    iii_is_p_set = set()
    q_bbdd_set = set()

    # child data fixed in this item
    c1_sex, c1_b, c1_d = c1
    c2_sex, c2_b, c2_d = c2

    # Enumerate parent X haplotypes (mom is XX -> ordered X1,X2; dad has one X)
    for momX in itertools.product(XHAPS, XHAPS):
        # Q is female, somatic b count is 1 in this template (kept fixed)
        if count_allele_in_female(momX[0], momX[1], "b") != 1:
            continue
        # Q d if observed
        qd = count_allele_in_female(momX[0], momX[1], "d")
        if q_d_obs is not None and q_d_obs != qd:
            continue

        for dadX in XHAPS:
            # In this template we keep child1/2 as “from P,Q”, no crossover, but need maternal pick branch
            for mom_pick_c1 in ["X1","X2"]:
                b1, d1 = child_bd_counts(momX, dadX, c1_sex, mom_pick_c1)
                if (b1,d1) != (c1_b,c1_d):
                    continue
                for mom_pick_c2 in ["X1","X2"]:
                    b2, d2 = child_bd_counts(momX, dadX, c2_sex, mom_pick_c2)
                    if (b2,d2) != (c2_b,c2_d):
                        continue

                    # Enumerate A genotypes
                    for dadA in AUTOG:
                        for momA in AUTOG:
                            # Assign which 2 cells belong to P
                            for P_cells in itertools.combinations(CELLS, 2):
                                owners = {c: ("P" if c in P_cells else "Q") for c in CELLS}

                                # Assign which 2 are 2n
                                for twon_cells in itertools.combinations(CELLS, 2):
                                    ploidy = {c: ("2n" if c in twon_cells else "n") for c in CELLS}

                                    male_n_cells = [c for c in CELLS if owners[c]=="P" and ploidy[c]=="n"]
                                    female_n_cells = [c for c in CELLS if owners[c]=="Q" and ploidy[c]=="n"]

                                    # Branch: male n is X-sperm or Y-sperm
                                    for male_types in itertools.product(["X","Y"], repeat=len(male_n_cells)):
                                        male_type_map = dict(zip(male_n_cells, male_types))

                                        # Branch: female n picks X1/X2
                                        for fx in itertools.product(["X1","X2"], repeat=len(female_n_cells)):
                                            fx_map = dict(zip(female_n_cells, fx))

                                            # Branch: A picks in gametes
                                            dadA_space = [0,1] if dadA=="Aa" else [0]
                                            momA_space = [0,1] if momA=="Aa" else [0]

                                            for mA_picks in itertools.product(momA_space, repeat=len(female_n_cells)):
                                                fA_map = dict(zip(female_n_cells, mA_picks))
                                                for dA_picks in itertools.product(dadA_space, repeat=len(male_n_cells)):
                                                    mA_map = dict(zip(male_n_cells, dA_picks))

                                                    # Match all cells
                                                    a_value: Optional[bool] = None
                                                    ok = True
                                                    for cell in CELLS:
                                                        exp = expected_presence_cell(
                                                            owner=owners[cell],
                                                            ploidy=ploidy[cell],
                                                            male_n_type=male_type_map.get(cell),
                                                            female_pickX=fx_map.get(cell),
                                                            female_pickA=fA_map.get(cell),
                                                            male_pickA=mA_map.get(cell),
                                                            dadA=dadA, momA=momA,
                                                            dadX=dadX, momX=momX,
                                                        )
                                                        for g in GENES_G:
                                                            ok, a_value = match_symbol(exp[g], obs_g[cell][g], a_value)
                                                            if not ok:
                                                                break
                                                        if not ok:
                                                            break
                                                    if not ok:
                                                        continue

                                                    # solution found
                                                    sols += 1
                                                    if a_value is not None:
                                                        a_set.add(a_value)
                                                    # statement ㄴ: III is P cell
                                                    iii_is_p_set.add(owners["III"] == "P")
                                                    # statement ㄷ: Q genotype is BbDd  <=> momX is {Bd, bD}
                                                    q_bbdd_set.add(set(momX) == {"Bd","bD"})

    return {
        "num_solutions": sols,
        "a_values": sorted(a_set),
        "III_is_P": sorted(iii_is_p_set),
        "Q_is_BbDd": sorted(q_bbdd_set),
    }

# =========================================
# World -> table generator (random underlying truth)
# =========================================
def random_world(rng: random.Random) -> Dict[str,Any]:
    """
    Build a consistent "truth world" then derive observed tables.
    Children: keep same as original:
      child1: male (b,d) = (0,1)
      child2: female (b,d) = (1,1)
      Q: female, b=1, d is variable (1 or 2) but can be masked
    """
    # Pick momX that satisfies Q b=1 AND can produce son(0,1) = Bd
    # easiest: force mom has Bd plus (bD or bd)
    mom_other = rng.choice(["bD","bd"])
    momX = ("Bd", mom_other)

    # Choose dadX so daughter2 can become (1,1)
    # if mom passes Bd -> dad must be bD
    # if mom passes bD -> dad must be Bd
    # if mom is Bd/bd and mom passes bd -> dad must be BD
    # We'll choose a maternal pick for daughter then solve dadX.
    mom_pick_dau = rng.choice(["X1","X2"])
    mh_dau = momX[0] if mom_pick_dau=="X1" else momX[1]

    if mh_dau == "Bd":
        dadX = "bD"
    elif mh_dau == "bD":
        dadX = "Bd"
    else:  # bd
        dadX = "BD"

    # Ensure son gets Bd (0,1): so mom_pick_son must pick the Bd haplotype => X1 here
    mom_pick_son = "X1"

    # A genotypes (any)
    dadA = rng.choice(AUTOG)
    momA = rng.choice(AUTOG)

    # Assign owners: choose 2 of 4 for P
    P_cells = set(rng.sample(CELLS, 2))
    owners = {c: ("P" if c in P_cells else "Q") for c in CELLS}

    # Assign ploidy: choose 2 for 2n
    twon_cells = set(rng.sample(CELLS, 2))
    ploidy = {c: ("2n" if c in twon_cells else "n") for c in CELLS}

    # Branch sperm type for P n-cells (X or Y)
    male_n_cells = [c for c in CELLS if owners[c]=="P" and ploidy[c]=="n"]
    male_n_type = {c: rng.choice(["X","Y"]) for c in male_n_cells}

    # Female egg picks for Q n-cells
    female_n_cells = [c for c in CELLS if owners[c]=="Q" and ploidy[c]=="n"]
    female_pickX = {c: rng.choice(["X1","X2"]) for c in female_n_cells}

    # A gamete picks
    dadA_space = [0,1] if dadA=="Aa" else [0]
    momA_space = [0,1] if momA=="Aa" else [0]
    male_pickA = {c: rng.choice(dadA_space) for c in male_n_cells}
    female_pickA = {c: rng.choice(momA_space) for c in female_n_cells}

    # Build full (unmasked) table (가) symbols
    true_g = {}
    for cell in CELLS:
        exp = expected_presence_cell(
            owner=owners[cell], ploidy=ploidy[cell],
            male_n_type=male_n_type.get(cell),
            female_pickX=female_pickX.get(cell),
            female_pickA=female_pickA.get(cell),
            male_pickA=male_pickA.get(cell),
            dadA=dadA, momA=momA, dadX=dadX, momX=momX,
        )
        true_g[cell] = {g: presence_symbol(exp[g]) for g in GENES_G}

    # (나) numeric truth
    qd = count_allele_in_female(momX[0], momX[1], "d")
    c1 = ("남",)  # fixed display strings
    # child outputs (fixed to match original format)
    c1_b, c1_d = child_bd_counts(momX, dadX, "M", mom_pick_son)
    c2_b, c2_d = child_bd_counts(momX, dadX, "F", mom_pick_dau)

    return {
        "dadA": dadA, "momA": momA,
        "dadX": dadX, "momX": momX,
        "owners": owners, "ploidy": ploidy,
        "male_n_type": male_n_type,
        "female_pickX": female_pickX,
        "male_pickA": male_pickA,
        "female_pickA": female_pickA,
        "true_g": true_g,
        "Q_b": 1, "Q_d": qd,
        "C1_sex": "남", "C1_b": c1_b, "C1_d": c1_d,
        "C2_sex": "여", "C2_b": c2_b, "C2_d": c2_d,
    }

# =========================================
# Masking + crafting (fixed <보기> like original)
# We keep statements:
# ㄱ ⓐ는 ‘×’이다.
# ㄴ III은 P의 세포이다.
# ㄷ Q의 (나)의 유전자형은 BbDd이다.
# =========================================
def make_observed_from_truth(rng: random.Random, truth_g: Dict[str,Dict[str,str]], qd: int, mask_p: float = 0.25) -> Tuple[Dict[str,Dict[str,str]], Optional[int]]:
    obs_g = {c: dict(truth_g[c]) for c in CELLS}

    # choose one position to be ⓐ (we'll use only one marker in A/B/D grid)
    a_cell = rng.choice(CELLS)
    a_gene = rng.choice(GENES_G)
    obs_g[a_cell][a_gene] = "a"

    # mask some cells to '?', but avoid nuking the ⓐ cell/gene
    for c in CELLS:
        for g in GENES_G:
            if c == a_cell and g == a_gene:
                continue
            if rng.random() < mask_p:
                obs_g[c][g] = "?"

    # Q d can be masked to '?'
    qd_obs: Optional[int] = qd if (rng.random() < 0.5) else None
    return obs_g, qd_obs

def invariants_to_truths(inv: Dict[str,Any]) -> Optional[Tuple[bool,bool,bool]]:
    """
    Determine whether ㄱㄴㄷ are invariant and return their truth values.
    If any is not invariant -> None.
    """
    if inv["num_solutions"] == 0:
        return None
    if len(inv["a_values"]) != 1:  # ⓐ not fixed
        return None
    if len(inv["III_is_P"]) != 1:
        return None
    if len(inv["Q_is_BbDd"]) != 1:
        return None

    # ㄱ: ⓐ는 ×이다.
    t1 = (inv["a_values"][0] is False)
    # ㄴ: III is P cell
    t2 = inv["III_is_P"][0]
    # ㄷ: Q is BbDd
    t3 = inv["Q_is_BbDd"][0]
    return (t1,t2,t3)

# =========================================
# Build BankItem
# =========================================
def build_item_from_seed(module: str, id_prefix: str, seed: int) -> Optional[BankItem]:
    rng = random.Random(seed)

    # generate truth world, then mask
    world = random_world(rng)
    obs_g, qd_obs = make_observed_from_truth(rng, world["true_g"], world["Q_d"], mask_p=rng.choice([0.20,0.25,0.30]))

    # solve and check invariants
    inv = solve_collect_invariants(
        obs_g=obs_g,
        q_d_obs=qd_obs,
        c1=("M", 0, 1),    # child1 male, (0,1) fixed in this template
        c2=("F", 1, 1),    # child2 female, (1,1)
    )
    truths = invariants_to_truths(inv)
    if truths is None:
        return None

    ans_idx = option_index(*truths)
    if ans_idx == -1:
        return None  # not representable by the ①~⑤ sets

    # Compose markdown
    table_md = (
        "### (가)\n"
        + render_table_g_md(obs_g)
        + "\n\n※ ○: 있음, ×: 없음\n\n"
        "### (나)\n"
        + render_table_n_md(
            sex_Q="여", q_b=1, q_d=qd_obs,
            c1_sex="남", c1_b=0, c1_d=1,
            c2_sex="여", c2_b=1, c2_d=1,
    )
)
    ask_line_md = (
        "이에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?\n\n"
        "<보 기>\n"
        "ㄱ. ⓐ는 ‘×’이다.\n"
        "ㄴ. III은 P의 세포이다.\n"
        "ㄷ. Q의 (나)의 유전자형은 BbDd이다.\n\n"
        "① ㄱ ② ㄴ ③ ㄱ, ㄷ ④ ㄴ, ㄷ ⑤ ㄱ, ㄴ, ㄷ"
    )
    answer_md = f"**정답:** {CHOICES[ans_idx]}"

    explanation_md = (
        f"- solver 가능한 해 수: **{inv['num_solutions']}**\n"
        f"- ⓐ 값(○/×) 불변: {inv['a_values']}\n"
        f"- ‘III이 P’ 불변: {inv['III_is_P']}\n"
        f"- ‘Q가 BbDd’ 불변: {inv['Q_is_BbDd']}\n"
        f"- 불변 진위 (ㄱ,ㄴ,ㄷ) = {truths} → {CHOICES[ans_idx]}"
    )

    return BankItem(
        id=new_id(id_prefix),
        module=module,
        id_prefix=id_prefix,
        problem_text_md=base_problem_text(),
        ask_line_md=ask_line_md,
        table_md=table_md,
        full_table_md=table_md,
        answer_md=answer_md,
        explanation_md=explanation_md,
        meta={
            "seed": seed,
            "invariants": inv,
            "truths": truths,
            # debug truth world (원하면 지워도 됨)
            "truth_world": {
                "dadA": world["dadA"], "momA": world["momA"],
                "dadX": world["dadX"], "momX": world["momX"],
                "owners": world["owners"],
                "ploidy": world["ploidy"],
                "true_g": world["true_g"],
                "Q_d_true": world["Q_d"],
            },
            "obs": {"g": obs_g, "Q_d_obs": qd_obs},
        }
    )

# =========================================
# Bank generation + output
# =========================================
def generate_bank(
    n: int,
    module: str,
    id_prefix: str,
    base_seed: int,
    max_tries_per_item: int = 20000,
) -> List[BankItem]:
    bank: List[BankItem] = []
    seed = base_seed
    while len(bank) < n:
        made = False
        for _ in range(max_tries_per_item):
            item = build_item_from_seed(module, id_prefix, seed)
            seed += 1
            if item is None:
                continue
            bank.append(item)
            made = True
            break
        if not made:
            raise RuntimeError("생성 실패: max_tries_per_item 증가 또는 마스킹 확률/규칙 완화 필요")
    return bank

def write_outputs(bank: List[BankItem], out_dir: str, pack_name: str, config: Dict[str,Any]) -> Tuple[str,str]:
    os.makedirs(out_dir, exist_ok=True)
    pack_str = pack_json(bank, pack_name=pack_name, config=config)

    json_path = os.path.join(out_dir, f"{pack_name}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(pack_str)

    md_path = os.path.join(out_dir, f"{pack_name}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        for i,item in enumerate(bank, 1):
            f.write(f"# {item.module} / {item.id}\n\n")
            f.write(item.problem_text_md + "\n\n")
            f.write(item.table_md + "\n\n")
            f.write(item.ask_line_md + "\n\n")
            f.write(item.answer_md + "\n\n")
            f.write("## 해설(내부)\n\n" + item.explanation_md + "\n\n")
            if i != len(bank):
                f.write("\n---\n\n")

    return json_path, md_path

# =========================================
# CLI
# =========================================
if __name__ == "__main__":
    MODULE = "26XLINK_G16"
    ID_PREFIX = "26XLINK_G16_"

    N = 30
    BASE_SEED = 20260130

    OUT_DIR = "./out/26XLINK_G16"
    PACK_NAME = "2606GENEDT_G16"

    bank = generate_bank(
        n=N,
        module=MODULE,
        id_prefix=ID_PREFIX,
        base_seed=BASE_SEED,
        max_tries_per_item=30000,  # 마스킹이 빡세면 늘려
    )

    json_path, md_path = write_outputs(
        bank,
        out_dir=OUT_DIR,
        pack_name=PACK_NAME,
        config={"module": MODULE, "n": N, "base_seed": BASE_SEED}
    )

    print("WROTE:")
    print(" -", json_path)
    print(" -", md_path)

