# family_linked_3loci_bank.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Tuple, Optional, Iterable
import itertools, random, time, uuid, json, os

# =========================
# Problem Bank schema
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

# 보기 선택지(너 코드에 원래 없어서 통과 시 NameError 터질 수 있음)
CHOICES = ["① ㄱ", "② ㄴ", "③ ㄷ", "④ ㄱ, ㄴ", "⑤ ㄴ, ㄷ"]

# =========================
# Genetics model (STRICT: same chromosome, NO crossover)
# =========================
HAPS = [A + B + D
        for A in ["A", "a"]
        for B in ["B", "b"]
        for D in ["D", "d"]]

ALLELES = ["A","a","B","b","D","d"]
LOCI = [("A","a"), ("B","b"), ("D","d")]
COLS = ["A","a","B","b","D","d"]
ROW_KEYS = ["I","II","III","IV"]

def hap_counts(h: str, mult: int) -> Dict[str,int]:
    c = {a:0 for a in ALLELES}
    c[h[0]] += mult
    c[h[1]] += mult
    c[h[2]] += mult
    return c

def dip_counts(h1: str, h2: str, mult: int) -> Dict[str,int]:
    c = {a:0 for a in ALLELES}
    for k,v in hap_counts(h1, mult=1).items():
        c[k] += v
    for k,v in hap_counts(h2, mult=1).items():
        c[k] += v
    if mult != 1:
        for a in ALLELES:
            c[a] *= mult
    return c

def genotype_str_from_haps(h1: str, h2: str) -> str:
    parts = []
    for i,(x,y) in enumerate(LOCI):
        a1 = h1[i]
        a2 = h2[i]
        pair = sorted([a1,a2], key=lambda z: (z.islower(), z))
        parts.append("".join(pair))
    return "".join(parts)

def stage_options_for_individual(h1: str, h2: str, stage: str) -> List[Dict[str,int]]:
    if stage == "G1":
        return [dip_counts(h1,h2,mult=1)]
    if stage == "MI":
        return [dip_counts(h1,h2,mult=2)]
    if stage == "MII":
        return [hap_counts(h1, mult=2), hap_counts(h2, mult=2)]
    if stage == "GAM":
        return [hap_counts(h1, mult=1), hap_counts(h2, mult=1)]
    raise ValueError("bad stage")

def chromatid_factor(stage: str) -> int:
    return {"G1":2, "MI":4, "MII":2, "GAM":1}[stage]

# =========================
# Markdown table rendering
# =========================
def render_table_md(rows: List[Dict[str,Any]]) -> str:
    header = ["세포 DNA 상대량"] + COLS
    out = []
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + "|".join(["---"]*len(header)) + "|")
    for r in rows:
        row = [r["label"]] + [str(r[c]) for c in COLS]
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)

def base_problem_text() -> str:
    return (
        "사람의 유전 형질 (가)는 같은 염색체에 있는 3쌍의 대립유전자 A/a, B/b, D/d에 의해 결정된다.\n"
        "표는 어떤 가족 구성원의 세포 Ⅰ～Ⅳ가 갖는 A, a, B, b, D, d의 DNA 상대량을 나타낸 것이다.\n"
        "Ⅰ은 G1기 세포이고, Ⅱ～Ⅳ는 감수 1분열 중기 세포, 감수 2분열 중기 세포, 생식세포를 순서 없이 나타낸 것이다.\n"
        "(단, 돌연변이와 교차는 고려하지 않으며 A, a, B, b, D, d 각각의 1개당 DNA 상대량은 1이다.) [3점]"
    )

# =========================
# Generator (haplotype-based, family-safe)
# =========================
def generate_candidate(seed: int, difficulty: int = 3) -> Dict[str,Any]:
    rng = random.Random(seed)

    # parents
    hf1, hf2 = rng.choice(HAPS), rng.choice(HAPS)
    hm1, hm2 = rng.choice(HAPS), rng.choice(HAPS)

    # kids (strict: one hap from each parent)
    son_hf = rng.choice([hf1,hf2]); son_hm = rng.choice([hm1,hm2])
    ds_hf  = rng.choice([hf1,hf2]); ds_hm  = rng.choice([hm1,hm2])

    target_is_daughter = (rng.random() < 0.5)
    target_key = "IV" if target_is_daughter else "III"

    # stages for II/III/IV
    stages = ["MI","MII","GAM"]
    rng.shuffle(stages)
    stage_of = {"II": stages[0], "III": stages[1], "IV": stages[2]}

    # true counts
    father_counts = stage_options_for_individual(hf1,hf2,"G1")[0]
    mother_counts = rng.choice(stage_options_for_individual(hm1,hm2,stage_of["II"]))
    son_counts    = rng.choice(stage_options_for_individual(son_hf,son_hm,stage_of["III"]))
    dau_counts    = rng.choice(stage_options_for_individual(ds_hf,ds_hm,stage_of["IV"]))

    rows_true = {"I":father_counts, "II":mother_counts, "III":son_counts, "IV":dau_counts}

    # mask
    q_p = {1:0.05, 2:0.10, 3:0.16, 4:0.22, 5:0.28}[int(difficulty)]
    observed = {k: dict(rows_true[k]) for k in ROW_KEYS}

    def maybe_q(k: str, col: str):
        if k == "I":
            if rng.random() < q_p * 0.35:
                observed[k][col] = "?"
        else:
            if rng.random() < q_p:
                observed[k][col] = "?"

    for k in ROW_KEYS:
        for col in COLS:
            maybe_q(k, col)

    # IMPORTANT: ensure each of II/III/IV has enough numeric info to lock stage
    def ensure_min_known(row_key: str, min_known: int = 4):
        vals = observed[row_key]
        unknown_cols = [c for c in COLS if vals[c] == "?"]
        known_cols = [c for c in COLS if vals[c] != "?"]
        if len(known_cols) >= min_known:
            return
        rng.shuffle(unknown_cols)
        need = min_known - len(known_cols)
        for c in unknown_cols[:need]:
            observed[row_key][c] = rows_true[row_key][c]

    for rk in ["II","III","IV"]:
        ensure_min_known(rk, min_known=4)

    # Place ⓐ and ⓑ in DIFFERENT rows among II/III/IV (prevents info collapse)
    rows_pick = ["II","III","IV"]
    rng.shuffle(rows_pick)
    a_k = rows_pick[0]
    b_k = rows_pick[1]
    a_c = rng.choice(COLS)
    b_c = rng.choice(COLS)

    a_real = rows_true[a_k][a_c]
    b_real = rows_true[b_k][b_c]
    observed[a_k][a_c] = "ⓐ"
    observed[b_k][b_c] = "ⓑ"

    # labels with ㉠
    son_label = "아들의 세포 Ⅲ"
    dau_label = "딸의 세포 Ⅳ"
    if target_is_daughter:
        dau_label = "㉠딸의 세포 Ⅳ"
    else:
        son_label = "㉠아들의 세포 Ⅲ"

    md_rows = [
        {"label":"아버지의 세포 Ⅰ", **observed["I"]},
        {"label":"어머니의 세포 Ⅱ", **observed["II"]},
        {"label":son_label, **observed["III"]},
        {"label":dau_label, **observed["IV"]},
    ]

    return {
        "rows_md": md_rows,
        "observed": observed,
        "stage_of_hidden": stage_of,
        "a_pos": (a_k,a_c),
        "b_pos": (b_k,b_c),
        # only keep target_key now; stmts will be crafted later
        "statements": {"target_key": target_key},
        "hidden_truth": {
            "hf": (hf1,hf2),
            "hm": (hm1,hm2),
            "son": (son_hf,son_hm),
            "dau": (ds_hf,ds_hm),
            "a_real": a_real,
            "b_real": b_real,
            "target_true": genotype_str_from_haps(ds_hf,ds_hm) if target_is_daughter else genotype_str_from_haps(son_hf,son_hm),
        }
    }

# =========================
# TRUE solver helpers
# =========================
def stage_permutations_for_II_III_IV() -> Iterable[Dict[str,str]]:
    for perm in itertools.permutations(["MI","MII","GAM"], 3):
        yield {"II":perm[0], "III":perm[1], "IV":perm[2]}

def all_parent_pairs() -> Iterable[Tuple[str,str]]:
    for i,h1 in enumerate(HAPS):
        for h2 in HAPS[i:]:
            yield (h1,h2)

def children_from_parents(hf: Tuple[str,str], hm: Tuple[str,str]) -> List[Tuple[str,str]]:
    out = []
    for a in hf:
        for b in hm:
            out.append((a,b))
    return out

def match_cell(expected: Dict[str,int], obs_cell: Dict[str,Any], var_assign: Dict[str,int]) -> Optional[Dict[str,int]]:
    newv = dict(var_assign)
    for col in COLS:
        ov = obs_cell[col]
        ev = expected[col]
        if ov == "?":
            continue
        if ov == "ⓐ":
            if "ⓐ" in newv and newv["ⓐ"] != ev:
                return None
            newv["ⓐ"] = ev
            continue
        if ov == "ⓑ":
            if "ⓑ" in newv and newv["ⓑ"] != ev:
                return None
            newv["ⓑ"] = ev
            continue
        if int(ov) != ev:
            return None
    return newv

# =========================
# Collect all consistent solutions (summary)
# =========================
def solve_collect(candidate: Dict[str,Any]) -> Dict[str,Any]:
    obs = candidate["observed"]

    sols = 0
    ab_sums = set()
    stage_maps = set()
    target_genos = set()
    a_values = set()
    b_values = set()

    for stage_of in stage_permutations_for_II_III_IV():
        for hf in all_parent_pairs():
            f_counts = stage_options_for_individual(hf[0],hf[1],"G1")[0]
            va1 = match_cell(f_counts, obs["I"], {})
            if va1 is None:
                continue

            for hm in all_parent_pairs():
                m_opts = stage_options_for_individual(hm[0],hm[1],stage_of["II"])
                child_pairs = children_from_parents(hf, hm)

                for m_counts in m_opts:
                    va2 = match_cell(m_counts, obs["II"], va1)
                    if va2 is None:
                        continue

                    for son_haps in child_pairs:
                        son_opts = stage_options_for_individual(son_haps[0],son_haps[1],stage_of["III"])
                        for son_counts in son_opts:
                            va3 = match_cell(son_counts, obs["III"], va2)
                            if va3 is None:
                                continue

                            for dau_haps in child_pairs:
                                dau_opts = stage_options_for_individual(dau_haps[0],dau_haps[1],stage_of["IV"])
                                for dau_counts in dau_opts:
                                    va4 = match_cell(dau_counts, obs["IV"], va3)
                                    if va4 is None:
                                        continue
                                    if "ⓐ" not in va4 or "ⓑ" not in va4:
                                        continue

                                    sols += 1
                                    a_values.add(va4["ⓐ"])
                                    b_values.add(va4["ⓑ"])
                                    ab_sums.add(va4["ⓐ"] + va4["ⓑ"])
                                    stage_maps.add((stage_of["II"], stage_of["III"], stage_of["IV"]))

                                    target_key = candidate["statements"]["target_key"]
                                    if target_key == "III":
                                        tg = genotype_str_from_haps(son_haps[0],son_haps[1])
                                    else:
                                        tg = genotype_str_from_haps(dau_haps[0],dau_haps[1])
                                    target_genos.add(tg)

    return {
        "num_solutions": sols,
        "a_values": sorted(a_values),
        "b_values": sorted(b_values),
        "ab_sums": sorted(ab_sums),
        "stage_maps": sorted(stage_maps),
        "target_genos": sorted(target_genos),
    }

# =========================
# Craft <보기> to force a unique option
# =========================
def option_index_family(t1: bool, t2: bool, t3: bool) -> int:
    # ① ㄱ ② ㄴ ③ ㄷ ④ ㄱ, ㄴ ⑤ ㄴ, ㄷ
    if t1 and (not t2) and (not t3): return 0
    if (not t1) and t2 and (not t3): return 1
    if (not t1) and (not t2) and t3: return 2
    if t1 and t2 and (not t3): return 3
    if (not t1) and t2 and t3: return 4
    return -1

def craft_statements_for_unique(candidate: Dict[str,Any], summary: Dict[str,Any]) -> Optional[Dict[str,Any]]:
    if summary["num_solutions"] == 0:
        return None

    # (핵심) 단계 배정이 유일하지 않으면 ㄴ을 고정하기 어려움 → 이 candidate는 버리는 편이 빠름
    if len(summary["stage_maps"]) != 1:
        return None

    # t3
    if len(summary["target_genos"]) == 1:
        t3_mode = "always_true"
        geno_claim = summary["target_genos"][0]
    else:
        t3_mode = "always_false"
        all_genos = set(genotype_str_from_haps(h1,h2) for h1 in HAPS for h2 in HAPS)
        cand_pool = sorted(all_genos - set(summary["target_genos"]))
        if not cand_pool:
            return None
        geno_claim = cand_pool[0]

    # t1
    if len(summary["ab_sums"]) == 1:
        t1_mode = "always_true"
        rhs = summary["ab_sums"][0]
    else:
        t1_mode = "always_false"
        rhs = 99  # impossible

    # t2: since stage_maps is unique now, we can freely choose any pair
    stage_of_tuple = summary["stage_maps"][0]
    mp = {"II": stage_of_tuple[0], "III": stage_of_tuple[1], "IV": stage_of_tuple[2]}
    pairs = [("II","III"),("II","IV"),("III","IV")]

    chosen_pair = None
    chosen_value = None
    for num,den in pairs:
        val = (chromatid_factor(mp[num]) / chromatid_factor(mp[den]) == 2)
        # Prefer making t2 True to allow option ② or ⑤
        if val:
            chosen_pair = (num,den)
            chosen_value = True
            break
    if chosen_pair is None:
        # otherwise pick first and it will be False
        chosen_pair = pairs[0]
        chosen_value = (chromatid_factor(mp[chosen_pair[0]]) / chromatid_factor(mp[chosen_pair[1]]) == 2)

    t1 = (t1_mode == "always_true")
    t2 = chosen_value
    t3 = (t3_mode == "always_true")

    opt = option_index_family(t1,t2,t3)
    if opt == -1:
        return None

    return {
        "stmt1": {"type":"sum_ab", "rhs": rhs},
        "stmt2": {"type":"chrom_ratio_eq2", "num": chosen_pair[0], "den": chosen_pair[1], "rhs": 2},
        "stmt3": {"type":"target_geno", "target": candidate["statements"]["target_key"], "claim": geno_claim},
        "forced_option": opt,
        "forced_truths": (t1,t2,t3),
    }

# =========================
# Build BankItem
# =========================
def build_bank_item(module: str, id_prefix: str, seed: int, difficulty: int = 3) -> BankItem:
    cand = generate_candidate(seed=seed, difficulty=difficulty)

    summary = solve_collect(cand)

    # (추가) 단계 배정이 유일해야 빠르게 성공
    if len(summary["stage_maps"]) != 1:
        raise ValueError("stage assignment not unique; resample")

    crafted = craft_statements_for_unique(cand, summary)
    if crafted is None:
        raise ValueError("cannot craft unique statements for this table")

    cand["statements"]["stmt1"] = crafted["stmt1"]
    cand["statements"]["stmt2"] = crafted["stmt2"]
    cand["statements"]["stmt3"] = crafted["stmt3"]

    ans_idx = crafted["forced_option"]

    table_md = render_table_md(cand["rows_md"])
    full_table_md = table_md

    rhs = cand["statements"]["stmt1"]["rhs"]
    num_key = cand["statements"]["stmt2"]["num"]
    den_key = cand["statements"]["stmt2"]["den"]
    geno_claim = cand["statements"]["stmt3"]["claim"]

    ask_line_md = (
        "이에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?\n\n"
        "<보 기>\n"
        f"ㄱ. ⓐ＋ⓑ＝{rhs}이다.\n"
        f"ㄴ. {num_key}의 염색 분체 수 / {den_key}의 염색 분체 수 ＝2이다.\n"
        f"ㄷ. ㉠의 (가)의 유전자형은 {geno_claim}이다.\n\n"
        "① ㄱ ② ㄴ ③ ㄷ ④ ㄱ, ㄴ ⑤ ㄴ, ㄷ"
    )

    answer_md = f"**정답:** {CHOICES[ans_idx]}"
    explanation_md = (
        f"- solver 가능한 해 수: **{summary['num_solutions']}**\n"
        f"- stage_maps(가능한 단계배정) = **{summary['stage_maps']}**\n"
        f"- ab_sums = {summary['ab_sums']}\n"
        f"- target_genos(개수) = {len(summary['target_genos'])}\n"
        f"- 후처리로 <보기>를 설계하여 정답을 **{CHOICES[ans_idx]}**로 고정(유일정답)\n"
        f"- (가족 안전) 자손은 항상 부모 하플로타입 조합으로만 인정(교차X) → 불가능 유전자형 배제"
    )

    return BankItem(
        id=new_id(id_prefix),
        module=module,
        id_prefix=id_prefix,
        problem_text_md=base_problem_text(),
        ask_line_md=ask_line_md,
        table_md=table_md,
        full_table_md=full_table_md,
        answer_md=answer_md,
        explanation_md=explanation_md,
        meta={
            "seed": seed,
            "difficulty": difficulty,
            "solver_summary": summary,
            "crafted": crafted,
            "hidden_truth": cand["hidden_truth"],         # 필요없으면 지워도 됨
            "stage_of_hidden": cand["stage_of_hidden"],   # 필요없으면 지워도 됨
        }
    )

# =========================
# Bank generation + output
# =========================
def generate_bank(
    n: int,
    module: str,
    id_prefix: str,
    difficulty: int,
    base_seed: int,
    max_tries_per_item: int = 5000,
) -> List[BankItem]:
    bank: List[BankItem] = []
    seed = base_seed
    while len(bank) < n:
        made = False
        for _ in range(max_tries_per_item):
            try:
                item = build_bank_item(module, id_prefix, seed=seed, difficulty=difficulty)
                bank.append(item)
                seed += 1
                made = True
                break
            except Exception:
                seed += 1
                continue
        if not made:
            raise RuntimeError("생성 실패: max_tries_per_item 증가 또는 마스킹/문장 생성 규칙 완화 필요")
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

# =========================
# CLI
# =========================
if __name__ == "__main__":
    MODULE = "2506GENEDETX"
    ID_PREFIX = "2506GENEDETX_"

    N = 30
    DIFF = 2
    BASE_SEED = 20260130

    OUT_DIR = "./out/2506GENEDETX"
    PACK_NAME = "2506GENEDETX"

    bank = generate_bank(
        n=N,
        module=MODULE,
        id_prefix=ID_PREFIX,
        difficulty=DIFF,
        base_seed=BASE_SEED,
        max_tries_per_item=12000,  # stage_maps=1 필터 때문에 좀 여유 줌
    )

    json_path, md_path = write_outputs(
        bank,
        out_dir=OUT_DIR,
        pack_name=PACK_NAME,
        config={"module": MODULE, "difficulty": DIFF, "n": N, "base_seed": BASE_SEED}
    )

    print("WROTE:")
    print(" -", json_path)
    print(" -", md_path)
