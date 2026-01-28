# matrix3_generator_PACK.py
# Matrix3 (일반유전) – L2I1(2연관+1독립) 전용 / 완전연관(교차 없음)
# ✅ 생성 실패 방지 최종판:
#   - 자손 조건(유전자형/표현형 확률)으로 먼저 좁히고
#   - 그래도 해(정답 후보)가 3개 초과면 "부모 조건(부모 표현형/부모 좌위 유전자형)"을 자동 추가해서 ≤3으로 강제
# ✅ pack 30개 안정 생성 목표

import os, json, time, random, hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Tuple, Any

MODULE = "MATRIX3"
ID_PREFIX = "MAT3_"
OUT_DIR = os.path.join(os.path.dirname(__file__), "output_pack")
os.makedirs(OUT_DIR, exist_ok=True)

# ----------------------------
# 기본 유틸
# ----------------------------

def frac_to_str(fr: Fraction) -> str:
    if fr.denominator == 1:
        return str(fr.numerator)
    return f"{fr.numerator}/{fr.denominator}"

def sha10(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:10]

def combine(a: str, b: str) -> str:
    return "".join(sorted([a, b], key=lambda c: (c.islower(), c)))

def is_dom(geno2: str, allele: str) -> int:
    return 1 if allele in geno2 else 0

def ph_label(gt: str) -> str:
    A2, B2, D2 = gt[0:2], gt[2:4], gt[4:6]
    return f"({ 'A+' if is_dom(A2,'A') else 'A-' },{ 'B+' if is_dom(B2,'B') else 'B-' },{ 'D+' if is_dom(D2,'D') else 'D-' })"

G1 = ["AA", "Aa", "aa"]

ALL_GT: List[str] = []
for A2 in ["AA", "Aa", "aa"]:
    for B2 in ["BB", "Bb", "bb"]:
        for D2 in ["DD", "Dd", "dd"]:
            ALL_GT.append(A2 + B2 + D2)

# ----------------------------
# 위상(phase) 생성
# ----------------------------

def phases2(gX: str, gY: str) -> List[Tuple[str, str]]:
    x = [gX[0], gX[1]]
    y = [gY[0], gY[1]]
    out = set()

    # coupling
    h1 = x[0] + y[0]
    h2 = x[1] + y[1]
    if sorted([h1[0], h2[0]]) == sorted(x) and sorted([h1[1], h2[1]]) == sorted(y):
        out.add(tuple(sorted([h1, h2])))

    # repulsion
    h1 = x[0] + y[1]
    h2 = x[1] + y[0]
    if sorted([h1[0], h2[0]]) == sorted(x) and sorted([h1[1], h2[1]]) == sorted(y):
        out.add(tuple(sorted([h1, h2])))

    return list(out)

def gam_phase(h1: str, h2: str) -> Dict[str, Fraction]:
    if h1 == h2:
        return {h1: Fraction(1)}
    return {h1: Fraction(1, 2), h2: Fraction(1, 2)}

def gam_single(g: str) -> Dict[str, Fraction]:
    a1, a2 = g[0], g[1]
    if a1 == a2:
        return {a1: Fraction(1)}
    return {a1: Fraction(1, 2), a2: Fraction(1, 2)}

# ----------------------------
# L2I1 자손 분포
# ----------------------------

def offspring_L2I1(linked: Tuple[str, str], P1: Dict[str, Any], P2: Dict[str, Any]) -> Dict[str, Fraction]:
    def gams(P: Dict[str, Any]) -> Dict[Tuple[str, str, str], Fraction]:
        gA, gB, gD = P["gA"], P["gB"], P["gD"]
        h1, h2 = P["phase2"]
        gp = gam_phase(h1, h2)

        if set(linked) == {"A", "B"}:
            gd = gam_single(gD)
            out: Dict[Tuple[str, str, str], Fraction] = {}
            for h, ph in gp.items():
                for d, pd in gd.items():
                    out[(h[0], h[1], d)] = out.get((h[0], h[1], d), Fraction(0)) + ph * pd
            return out

        if set(linked) == {"A", "D"}:
            gb = gam_single(gB)
            out: Dict[Tuple[str, str, str], Fraction] = {}
            for h, ph in gp.items():
                for b, pb in gb.items():
                    out[(h[0], b, h[1])] = out.get((h[0], b, h[1]), Fraction(0)) + ph * pb
            return out

        if set(linked) == {"B", "D"}:
            ga = gam_single(gA)
            out: Dict[Tuple[str, str, str], Fraction] = {}
            for h, ph in gp.items():
                for a, pa in ga.items():
                    out[(a, h[0], h[1])] = out.get((a, h[0], h[1]), Fraction(0)) + ph * pa
            return out

        raise RuntimeError("invalid linked")

    g1 = gams(P1)
    g2 = gams(P2)

    dist: Dict[str, Fraction] = {}
    for (a1, b1, d1), p1 in g1.items():
        for (a2, b2, d2), p2 in g2.items():
            A2 = combine(a1, a2)
            B2 = combine(b1, b2)
            D2 = combine(d1, d2)
            gt = A2 + B2 + D2
            dist[gt] = dist.get(gt, Fraction(0)) + p1 * p2

    s = sum(dist.values(), Fraction(0))
    if s != 1:
        for k in list(dist.keys()):
            dist[k] /= s
    return dist

def ph_dist(dist: Dict[str, Fraction]) -> Dict[str, Fraction]:
    out: Dict[str, Fraction] = {}
    for gt, pr in dist.items():
        lab = ph_label(gt)
        out[lab] = out.get(lab, Fraction(0)) + pr
    return out

def ph_count_of_dist(dist: Dict[str, Fraction]) -> int:
    pd = ph_dist(dist)
    return sum(1 for v in pd.values() if v > 0)

# ----------------------------
# 부모 후보 생성 (L2I1)
# ----------------------------

def enum_parents_L2I1(linked: Tuple[str, str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for gA in G1:
        for gB in G1:
            for gD in G1:
                if set(linked) == {"A", "B"}:
                    phs = phases2(gA, gB)
                    for ph in phs:
                        out.append({"gA": gA, "gB": gB, "gD": gD, "phase2": ph})
                elif set(linked) == {"A", "D"}:
                    phs = phases2(gA, gD)
                    for ph in phs:
                        out.append({"gA": gA, "gB": gB, "gD": gD, "phase2": ph})
                elif set(linked) == {"B", "D"}:
                    phs = phases2(gB, gD)
                    for ph in phs:
                        out.append({"gA": gA, "gB": gB, "gD": gD, "phase2": ph})
                else:
                    raise RuntimeError("invalid linked")
    return out

def pstr_L2I1(P: Dict[str, Any]) -> str:
    g = P["gA"] + P["gB"] + P["gD"]
    return f"{g} (연관상:{P['phase2'][0]}/{P['phase2'][1]})"

def parent_ph(P: Dict[str, Any]) -> str:
    A = "A+" if ("A" in P["gA"]) else "A-"
    B = "B+" if ("B" in P["gB"]) else "B-"
    D = "D+" if ("D" in P["gD"]) else "D-"
    return f"({A},{B},{D})"

# ----------------------------
# 사전계산 Pair 테이블
# ----------------------------

@dataclass(frozen=True)
class PairInfo:
    idx1: int
    idx2: int
    ph_count: int
    dist: Dict[str, Fraction]

@dataclass
class CaseCache:
    linked: Tuple[str, str]
    cands: List[Dict[str, Any]]
    pairs: List[PairInfo]

def build_case_cache(linked: Tuple[str, str]) -> CaseCache:
    cands = enum_parents_L2I1(linked)
    pairs: List[PairInfo] = []

    # unordered(i<=j)로 저장
    for i in range(len(cands)):
        for j in range(i, len(cands)):
            d = offspring_L2I1(linked, cands[i], cands[j])
            pc = ph_count_of_dist(d)
            pairs.append(PairInfo(i, j, pc, d))

    return CaseCache(linked=linked, cands=cands, pairs=pairs)

# ----------------------------
# 후보 필터링 도구
# ----------------------------

def filter_pairs_by_child_conds(case: CaseCache, ph_count: int, child_conds: List[Tuple[str, str, Fraction]]) -> List[int]:
    """
    child_conds: [("GT", genotype, prob), ("PH", phenotype_label, prob), ...]
    반환: case.pairs 인덱스 리스트
    """
    out = []
    for idx, p in enumerate(case.pairs):
        if p.ph_count != ph_count:
            continue
        d = p.dist
        ph_cache = None
        ok = True
        for typ, key, pr in child_conds:
            if typ == "GT":
                if d.get(key, Fraction(0)) != pr:
                    ok = False
                    break
            else:  # PH
                if ph_cache is None:
                    ph_cache = ph_dist(d)
                if ph_cache.get(key, Fraction(0)) != pr:
                    ok = False
                    break
        if ok:
            out.append(idx)
    return out

def filter_sols_by_parent_constraint(case: CaseCache, cand_pair_idxs: List[int], constraint: Tuple[str, int, str]) -> List[int]:
    """
    constraint: (kind, who, value)
    kind: "PH" or "GA"/"GB"/"GD"
    who: 1 or 2
    """
    kind, who, value = constraint
    out = []
    for pidx in cand_pair_idxs:
        p = case.pairs[pidx]
        P = case.cands[p.idx1] if who == 1 else case.cands[p.idx2]
        if kind == "PH":
            if parent_ph(P) == value:
                out.append(pidx)
        elif kind == "GA":
            if P["gA"] == value:
                out.append(pidx)
        elif kind == "GB":
            if P["gB"] == value:
                out.append(pidx)
        elif kind == "GD":
            if P["gD"] == value:
                out.append(pidx)
    return out

# ----------------------------
# 문제 생성 (안전장치: 부모조건 자동 추가)
# ----------------------------

@dataclass
class Problem:
    pid: str
    payload: Dict[str, Any]

def build_one(case_caches: Dict[Tuple[str, str], CaseCache],
              max_seed_tries: int = 5000) -> Problem:
    lopts = [("A", "B"), ("A", "D"), ("B", "D")]

    for _ in range(max_seed_tries):
        linked = random.choice(lopts)
        case = case_caches[linked]

        # seed = 임의의 pair 하나 잡기 (사전계산이 있으니 빠름)
        seed = random.choice(case.pairs)
        dist = seed.dist
        ph_count = seed.ph_count
        if not (3 <= ph_count <= 6):
            continue

        # --- 자손 조건 풀 (seed의 "진짜 값" 기반) ---
        gt_pool = [("GT", gt, dist.get(gt, Fraction(0))) for gt in ALL_GT]

        ph = ph_dist(dist)
        ph_pool = [("PH", lab, pr) for lab, pr in ph.items() if pr > 0]

        # 정보량 높은 것(0/1 아닌 것) 우선
        def info_score(pr: Fraction) -> int:
            return 0 if (pr != 0 and pr != 1) else 1

        gt_pool.sort(key=lambda x: info_score(x[2]))
        ph_pool.sort(key=lambda x: info_score(x[2]))

        child_pool = ph_pool + gt_pool  # PH 먼저(대칭해 절단에 유리)

        # --- 그리디로 자손 조건부터 붙여서 후보 줄이기 ---
        child_conds: List[Tuple[str, str, Fraction]] = []
        cand_idxs = list(range(len(case.pairs)))
        # 같은 ph_count만으로 1차 필터
        cand_idxs = [i for i, p in enumerate(case.pairs) if p.ph_count == ph_count]
        if not cand_idxs:
            continue

        # 조건을 최대 10개까지 자손에서만 붙여봄
        for _k in range(10):
            if len(cand_idxs) <= 3:
                break

            best = None
            best_size = None
            for cond in child_pool:
                if cond in child_conds:
                    continue
                filtered = filter_pairs_by_child_conds(case, ph_count, child_conds + [cond])
                if not filtered:
                    continue
                # seed 포함 보장(정답이 seed dist여야 하니까)
                # (seed와 같은 dist를 만드는 동치해가 있을 수 있으므로 seed 자체 인덱스는 몰라도,
                #  "seed dist값" 조건을 쓰고 있으니 filtered는 반드시 seed 동치해를 포함함)
                s = len(filtered)
                if best is None or s < best_size:
                    best = cond
                    best_size = s
                    if s <= 3:
                        break

            if best is None:
                break
            child_conds.append(best)
            cand_idxs = filter_pairs_by_child_conds(case, ph_count, child_conds)

        # --- 여기서도 3개 초과면: 부모조건을 자동 추가해서 강제로 ≤3 만들기 ---
        parent_constraints: List[Tuple[str, int, str]] = []

        if len(cand_idxs) > 3:
            pool: List[Tuple[str, int, str]] = []
            ph_vals = [
                "(A+,B+,D+)", "(A+,B+,D-)", "(A+,B-,D+)", "(A+,B-,D-)",
                "(A-,B+,D+)", "(A-,B+,D-)", "(A-,B-,D+)", "(A-,B-,D-)",
            ]
            for who in [1, 2]:
                for phv in ph_vals:
                    pool.append(("PH", who, phv))
                for g in ["AA", "Aa", "aa"]:
                    pool.append(("GA", who, g))
                for g in ["BB", "Bb", "bb"]:
                    pool.append(("GB", who, g))
                for g in ["DD", "Dd", "dd"]:
                    pool.append(("GD", who, g))

            random.shuffle(pool)

            # 최대 6개 부모조건까지 붙여서 줄이기
            for c in pool:
                reduced = filter_sols_by_parent_constraint(case, cand_idxs, c)
                if not reduced:
                    continue
                if len(reduced) < len(cand_idxs):
                    parent_constraints.append(c)
                    cand_idxs = reduced
                if len(cand_idxs) <= 3:
                    break

        if not (1 <= len(cand_idxs) <= 3):
            continue  # 이 seed는 포기하고 다음

        # 최종 솔루션 리스트(≤3)
        final_sols = [(case.pairs[i].idx1, case.pairs[i].idx2) for i in cand_idxs]

        # ---------- 문제 텍스트 ----------
        problem_code = f"M3-{random.randint(1,999):03d}"
        pid = ID_PREFIX + sha10(f"{time.time()}_{problem_code}_{random.random()}")

        lg = list(linked)
        link_desc = f"({lg[0]}/{lg[0].lower()}), ({lg[1]}/{lg[1].lower()})는 연관이며 교차 없음(완전연관). 나머지 1쌍은 독립이다."

        ph_desc = (
            "※ 표현형은 **각 유전자의 우성 발현 여부(A+/B+/D+)**로 구분한다.\n"
            "- A 유전자에 'A'가 1개 이상 있으면(Aa, AA) 발현(A+), 없으면(aa) 비발현(A-)\n"
            "- B 유전자에 'B'가 1개 이상 있으면(Bb, BB) 발현(B+), 없으면(bb) 비발현(B-)\n"
            "- D 유전자에 'D'가 1개 이상 있으면(Dd, DD) 발현(D+), 없으면(dd) 비발현(D-)\n"
            "따라서 표현형은 (A+/A-, B+/B-, D+/D-) 형태로 나타난다.\n"
        )

        cond_lines = []
        # 자손 조건
        for typ, key, pr in child_conds:
            if typ == "GT":
                cond_lines.append(f"- 자손 유전자형 **{key}** 의 확률 = **{frac_to_str(pr)}**")
            else:
                cond_lines.append(f"- 자손 표현형 **{key}** 의 확률 = **{frac_to_str(pr)}**")

        # 부모 조건(필요할 때만 붙음)
        for kind, who, val in parent_constraints:
            if kind == "PH":
                cond_lines.append(f"- 부모 P{who}의 표현형은 **{val}** 이다.")
            elif kind == "GA":
                cond_lines.append(f"- 부모 P{who}의 A좌위 유전자형은 **{val}** 이다.")
            elif kind == "GB":
                cond_lines.append(f"- 부모 P{who}의 B좌위 유전자형은 **{val}** 이다.")
            elif kind == "GD":
                cond_lines.append(f"- 부모 P{who}의 D좌위 유전자형은 **{val}** 이다.")

        problem_text_md = (
            f"문제 제목 : Matrix3 일반유전 추론 ({problem_code})\n\n"
            f"(A/a), (B/b), (D/d) 세 유전자는 각각 다른 형질을 결정한다(일반유전).\n"
            f"{link_desc}\n\n"
            f"- 부모 P1, P2는 미지수이다.\n"
            f"- 자손의 **표현형 종류는 {ph_count}가지**이다.\n"
            + "\n".join(cond_lines) + "\n\n"
            + ph_desc
            + "조건을 만족하는 모든 (P1,P2) 조합을 구하시오."
        )

        ask_line_md = "가능한 모든 P1, P2 조합을 구하고, 자손 표현형의 종류와 각 확률을 구하시오."

        # ---------- 정답 ----------
        answer_lines: List[str] = []
        answer_lines.append(f"총 정답 후보: {len(final_sols)}개\n")

        for idx_s, (i1, i2) in enumerate(final_sols, 1):
            c1 = case.cands[i1]
            c2 = case.cands[i2]
            answer_lines.append(f"[후보 {idx_s}]")
            answer_lines.append(f"- P1 = {pstr_L2I1(c1)}")
            answer_lines.append(f"- P2 = {pstr_L2I1(c2)}")

            sol_dist = offspring_L2I1(linked, c1, c2)
            sol_ph = ph_dist(sol_dist)
            for k in sorted(sol_ph.keys()):
                if sol_ph[k] > 0:
                    answer_lines.append(f"  - {k} : {frac_to_str(sol_ph[k])}")
            answer_lines.append("")

        answer_text_md = "\n".join(answer_lines)

        solution_md = (
            "### 해설(자동)\n"
            "- L2I1 완전연관에서는 서로 다른 부모쌍이 동일한 자손 분포를 만들 수 있어(동치해) 자손 조건만으로는 해가 잘 안 줄 수 있다.\n"
            "- 따라서 먼저 자손(유전자형/표현형 확률) 조건으로 후보를 줄이고,\n"
            "  그래도 정답 후보가 3개를 초과하면 부모 표현형/부모 좌위 유전자형 조건을 자동으로 추가하여 1~3개로 만든다.\n"
        )

        payload = {
            "module": MODULE,
            "id_prefix": ID_PREFIX,
            "problem_code": problem_code,
            "pattern": "L2I1",
            "linked_genes": list(linked),
            "constraints": {
                "phenotype_count": ph_count,
                "child_conditions": [{"type": typ, "key": key, "prob": frac_to_str(pr)} for (typ, key, pr) in child_conds],
                "parent_conditions": [{"kind": k, "who": w, "value": v} for (k, w, v) in parent_constraints],
            },
            "solutions": [
                {"P1": pstr_L2I1(case.cands[i1]), "P2": pstr_L2I1(case.cands[i2])}
                for (i1, i2) in final_sols
            ],
            "problem_text_md": problem_text_md,
            "ask_line_md": ask_line_md,
            "answer_text_md": answer_text_md,
            "solution_md": solution_md,
        }

        return Problem(pid, payload)

    raise RuntimeError("문제 생성 실패: 조건 완화 필요 (tries 증가 필요)")

# ----------------------------
# PACK 저장
# ----------------------------

def make_pack(n: int = 30) -> str:
    case_caches: Dict[Tuple[str, str], CaseCache] = {}
    for linked in [("A", "B"), ("A", "D"), ("B", "D")]:
        case_caches[linked] = build_case_cache(linked)

    items: List[Dict[str, Any]] = []
    for i in range(1, n + 1):
        pr = build_one(case_caches, max_seed_tries=5000)
        items.append({
            "id": pr.pid,
            "pid": pr.pid,
            "module": MODULE,
            "id_prefix": ID_PREFIX,
            "difficulty": 2,
            "problem_text_md": pr.payload["problem_text_md"],
            "ask_line_md": pr.payload["ask_line_md"],
            "answer_text_md": pr.payload["answer_text_md"],
            "solution_md": pr.payload["solution_md"],
            "payload": pr.payload,
            "_qnum": i
        })

    pack = {
        "module": MODULE,
        "id_prefix": ID_PREFIX,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "items": items
    }

    out_path = os.path.join(OUT_DIR, f"pack_{MODULE}_{int(time.time())}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)

    return out_path

if __name__ == "__main__":
    print("[OK] PACK saved:", make_pack(30))