# matrix3_generator_PACK.py
# Matrix3 (일반유전) – L2I1(2연관+1독립) 전용 / 완전연관(교차 없음)
# ✅ 파일 전체 교체용 (사전계산 seed 방식 + unordered 솔루션 카운트 + 0조건 우선 강화)
# ✅ 정답 후보는 최대 3개(>3이면 조건을 자동으로 추가해 줄임)
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
    # 대문자 우선 + 알파벳 기준 정렬로 "Aa" 형태 고정
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

PRETTY = {
    Fraction(1, 16), Fraction(3, 16),
    Fraction(1, 8),  Fraction(3, 8),
    Fraction(1, 4),  Fraction(3, 4),
    Fraction(1, 2),  Fraction(9, 16),
}

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

def pstr_L2I1(P: Dict[str, Any], linked: Tuple[str, str]) -> str:
    g = P["gA"] + P["gB"] + P["gD"]
    return f"{g} (연관상:{P['phase2'][0]}/{P['phase2'][1]})"

# ----------------------------
# 사전계산 + seed
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
    seeds: List[int]

def build_case_cache(linked: Tuple[str, str]) -> CaseCache:
    cands = enum_parents_L2I1(linked)
    pairs: List[PairInfo] = []

    # ✅ unordered pair만 저장 (i <= j) : (P1,P2) vs (P2,P1) 중복으로 해가 2배되는 문제 제거
    for i in range(len(cands)):
        for j in range(i, len(cands)):
            d = offspring_L2I1(linked, cands[i], cands[j])
            pc = ph_count_of_dist(d)
            pairs.append(PairInfo(i, j, pc, d))

    # seed 기준: 너무 빡세게 잡으면 seed가 쓸모 없어짐 -> 느슨하게
    seeds: List[int] = []
    for k, p in enumerate(pairs):
        if not (3 <= p.ph_count <= 6):
            continue
        zeros = sum(1 for gt in ALL_GT if p.dist.get(gt, Fraction(0)) == 0)
        if zeros < 2:
            continue
        pos = sum(1 for v in p.dist.values() if v > 0)
        if pos < 4:
            continue
        seeds.append(k)

    return CaseCache(linked=linked, cands=cands, pairs=pairs, seeds=seeds)

# ----------------------------
# 해 탐색(≤3 초과면 중단) - unordered라 sols도 unordered
# ----------------------------

def count_solutions_upto3(case: CaseCache, ph_count: int, conds: List[Tuple[str, str, Fraction]]) -> List[Tuple[int, int]]:
    """
    conds: [("GT", genotype, prob), ("PH", phenotype_label, prob), ...]
    """
    sols: List[Tuple[int, int]] = []
    for p in case.pairs:
        if p.ph_count != ph_count:
            continue

        d = p.dist
        ok = True

        # PH 분포는 필요할 때만 계산(속도)
        ph_cache = None

        for typ, key, pr in conds:
            if typ == "GT":
                if d.get(key, Fraction(0)) != pr:
                    ok = False
                    break
            elif typ == "PH":
                if ph_cache is None:
                    ph_cache = ph_dist(d)
                if ph_cache.get(key, Fraction(0)) != pr:
                    ok = False
                    break
            else:
                raise RuntimeError("invalid condition type")

        if ok:
            sols.append((p.idx1, p.idx2))
            if len(sols) > 3:
                return sols
    return sols

# ----------------------------
# 문제 생성
# ----------------------------

@dataclass
class Problem:
    pid: str
    payload: Dict[str, Any]

def build_one(case_caches: Dict[Tuple[str, str], CaseCache],
              max_seed_tries: int = 20000) -> Problem:

    lopts = [("A", "B"), ("A", "D"), ("B", "D")]

    for _ in range(max_seed_tries):
        linked = random.choice(lopts)
        case = case_caches[linked]
        if not case.seeds:
            continue

        seed_idx = random.choice(case.seeds)
        seed = case.pairs[seed_idx]
        dist = seed.dist
        ph_count = seed.ph_count

        # 후보 풀 만들기
        zeros = [gt for gt in ALL_GT if dist.get(gt, Fraction(0)) == 0]
        pos_all = [(gt, pr) for gt, pr in dist.items() if pr > 0]
        if len(zeros) < 2 or len(pos_all) < 2:
            continue

        # “예쁜 분수” 우선 정렬 (없어도 됨)
        pos_pretty = [(gt, pr) for gt, pr in pos_all if pr in PRETTY]
        pos_pool = pos_pretty + pos_all if pos_pretty else pos_all

        # 표현형 후보(0/1 제외: 정보량 낮음)
        ph = ph_dist(dist)
        ph_pool = [(lab, pr) for lab, pr in ph.items() if pr not in (Fraction(0), Fraction(1))]
        if not ph_pool:
            # 그래도 PH 조건이 없으면 GT만으로 시도는 하되 성공률이 낮음
            ph_pool = [(lab, pr) for lab, pr in ph.items() if pr > 0]

        # ---- 여기서부터 “조건 조합 탐색” ----
        # 1) GT+ (1개) + GT0 (2개) + PH (1개) 를 먼저 탐색 (가장 잘 잘림)
        found = None  # (final_conds, final_sols)

        # 탐색 폭 제한(속도): 너무 많으면 일부만 샘플
        ZS = zeros if len(zeros) <= 10 else random.sample(zeros, 10)
        PS = pos_pool if len(pos_pool) <= 10 else random.sample(pos_pool, 10)
        HS = ph_pool if len(ph_pool) <= 8 else random.sample(ph_pool, 8)

        for (gt1, pr1) in PS:
            for i in range(len(ZS)):
                for j in range(i + 1, len(ZS)):
                    z1, z2 = ZS[i], ZS[j]
                    for (hlab, hpr) in HS:
                        conds = [("GT", gt1, pr1), ("GT", z1, Fraction(0)), ("GT", z2, Fraction(0)),
                                 ("PH", hlab, hpr)]
                        sols = count_solutions_upto3(case, ph_count, conds)
                        if 1 <= len(sols) <= 3:
                            found = (conds, sols)
                            break
                    if found: break
                if found: break
            if found: break

        # 2) 아직도 못 찾았으면 GT+ 하나 더 추가해서(=5조건) 강제
        if found is None:
            for (gt1, pr1) in PS:
                for i in range(len(ZS)):
                    for j in range(i + 1, len(ZS)):
                        z1, z2 = ZS[i], ZS[j]
                        for (hlab, hpr) in HS:
                            for (gt2, pr2) in PS:
                                if gt2 == gt1:
                                    continue
                                conds = [("GT", gt1, pr1), ("GT", z1, Fraction(0)), ("GT", z2, Fraction(0)),
                                         ("PH", hlab, hpr), ("GT", gt2, pr2)]
                                sols = count_solutions_upto3(case, ph_count, conds)
                                if 1 <= len(sols) <= 3:
                                    found = (conds, sols)
                                    break
                            if found: break
                        if found: break
                    if found: break
                if found: break

        if found is None:
            continue  # 다른 seed로

        final_conds, final_sols = found

        # ---------- 문제 텍스트 ----------
        problem_code = f"M3-{random.randint(1,999):03d}"
        pid = ID_PREFIX + sha10(f"{time.time()}_{problem_code}_{random.random()}")

        lg = list(linked)
        link_desc = f"({lg[0]}/{lg[0].lower()}), ({lg[1]}/{lg[1].lower()})는 연관이며 교차 없음(완전연관). 나머지 1쌍은 독립이다."

        ph_desc = (
            "※ 표현형은 **대문자 개수(k)**가 아니라, 각 유전자의 **우성 표현 여부(A+/B+/D+)**로 구분한다.\n"
            "- A형질: A-이면 발현, aa이면 비발현\n"
            "- B형질: B-이면 발현, bb이면 비발현\n"
            "- D형질: D-이면 발현, dd이면 비발현\n"
            "따라서 표현형은 (A+/A-, B+/B-, D+/D-) 형태로 나타난다.\n"
        )

        cond_lines = []
        for typ, key, pr in final_conds:
            if typ == "GT":
                if pr == 0:
                    cond_lines.append(f"- 자손 유전자형 **{key}** 의 확률 = **0**")
                else:
                    cond_lines.append(f"- 자손 유전자형 **{key}** 의 확률 = **{frac_to_str(pr)}**")
            else:  # PH
                cond_lines.append(f"- 자손 표현형 **{key}** 의 확률 = **{frac_to_str(pr)}**")

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

        answer_lines: List[str] = []
        answer_lines.append(f"총 정답 후보: {len(final_sols)}개\n")

        for idx_s, (i1, i2) in enumerate(final_sols, 1):
            c1 = case.cands[i1]
            c2 = case.cands[i2]
            answer_lines.append(f"[후보 {idx_s}]")
            answer_lines.append(f"- P1 = {pstr_L2I1(c1, linked)}")
            answer_lines.append(f"- P2 = {pstr_L2I1(c2, linked)}")

            sol_dist = offspring_L2I1(linked, c1, c2)
            sol_ph = ph_dist(sol_dist)
            for k in sorted(sol_ph.keys()):
                if sol_ph[k] > 0:
                    answer_lines.append(f"  - {k} : {frac_to_str(sol_ph[k])}")
            answer_lines.append("")

        answer_text_md = "\n".join(answer_lines)

        solution_md = (
            "### 해설(자동)\n"
            "- 완전연관(L2I1)에서는 유전자형 조건만으로는 동치해가 많이 남을 수 있다.\n"
            "- 그래서 (유전자형 + 0조건 2개 + 표현형 확률 1개)를 기본으로 사용하고,\n"
            "  필요하면 유전자형 확률 조건을 1개 더 추가해 정답 후보를 1~3개로 줄였다.\n"
        )

        payload = {
            "module": MODULE,
            "id_prefix": ID_PREFIX,
            "problem_code": problem_code,
            "pattern": "L2I1",
            "linked_genes": list(linked),
            "constraints": {
                "phenotype_count": ph_count,
                "conditions": [
                    {"type": typ, "key": key, "prob": ("0" if pr == 0 else frac_to_str(pr))}
                    for (typ, key, pr) in final_conds
                ],
            },
            "solutions": [
                {
                    "P1": pstr_L2I1(case.cands[i1], linked),
                    "P2": pstr_L2I1(case.cands[i2], linked),
                }
                for (i1, i2) in final_sols
            ],
            "problem_text_md": problem_text_md,
            "ask_line_md": ask_line_md,
            "answer_text_md": answer_text_md,
            "solution_md": solution_md,
        }

        return Problem(pid, payload)

    raise RuntimeError("문제 생성 실패: 조건 완화 필요 (탐색 범위 내에서 유효 조건 조합을 못 찾음)")

# ----------------------------
# PACK 저장
# ----------------------------

def make_pack(n: int = 30) -> str:
    case_caches: Dict[Tuple[str, str], CaseCache] = {}
    for linked in [("A", "B"), ("A", "D"), ("B", "D")]:
        case_caches[linked] = build_case_cache(linked)
        # 디버그(필요시)
        # print("[cache]", linked, "cands=", len(case_caches[linked].cands),
        #       "pairs=", len(case_caches[linked].pairs),
        #       "seeds=", len(case_caches[linked].seeds))

    items: List[Dict[str, Any]] = []
    for i in range(1, n + 1):
        pr = build_one(case_caches, max_seed_tries=20000)
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
