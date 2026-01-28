# matrix3_generator_PACK.py
# Matrix3 (일반유전) – L2I1(2연관+1독립) 전용 / 완전연관(교차 없음)
# ✅ 파일 전체 교체용 (사전계산 seed 방식 + unordered 솔루션 카운트 + 0조건 우선 강화)
# ✅ 정답 후보는 최대 3개(>3이면 조건을 자동으로 추가해 줄임)
# ✅ pack 30개 안정 생성 목표

import os, json, time, random, hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Tuple, Optional, Any

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
        if pos < 6:
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

    # ✅ 조건 개수 상한: 실패 없애려면 넉넉히
    # (대부분 4~8개에서 끝남. 최악 대비로 20 정도 추천)
    MAX_CONDS = 20

    # 조건 후보 풀을 만들 때, 정보량 낮은(0,1) 확률은 우선순위 낮춤
    def is_low_info_prob(p: Fraction) -> bool:
        return p == 0 or p == 1

    # 한 condition을 적용해서 후보를 필터링
    def filter_candidates(cands_idx: List[int], case: CaseCache, cond: Tuple[str, str, Fraction]) -> List[int]:
        typ, key, pr = cond
        out = []
        for idx in cands_idx:
            d = case.pairs[idx].dist
            if typ == "GT":
                if d.get(key, Fraction(0)) == pr:
                    out.append(idx)
            else:  # "PH"
                ph = ph_dist(d)
                if ph.get(key, Fraction(0)) == pr:
                    out.append(idx)
        return out

    # 그리디로 “가장 많이 줄이는” 조건 선택
    def pick_best_cond(cands_idx: List[int], case: CaseCache, cond_pool: List[Tuple[str, str, Fraction]]) -> Optional[Tuple[str, str, Fraction]]:
        best = None
        best_size = None
        for cond in cond_pool:
            filtered = filter_candidates(cands_idx, case, cond)
            if not filtered:
                continue
            # 후보를 더 많이 줄이는(=사이즈가 더 작은) 조건 선호
            s = len(filtered)
            if best is None or s < best_size:
                best = cond
                best_size = s
                if best_size == 1:  # 더 줄일 수 없음
                    return best
        return best

    for _ in range(max_seed_tries):
        linked = random.choice(lopts)
        case = case_caches[linked]
        if not case.seeds:
            continue

        seed_idx = random.choice(case.seeds)
        seed = case.pairs[seed_idx]
        dist = seed.dist
        ph_count = seed.ph_count

        # 시작 후보: 같은 ph_count를 가진 모든 pair 인덱스
        cand_idx = [i for i, p in enumerate(case.pairs) if p.ph_count == ph_count]
        if not cand_idx:
            continue

        # seed 분포에서 “정답(=seed)”의 실제 값들로 조건 풀 구성
        # GT 조건: 27개 전부 (0 포함) -> 결국 dist를 거의 특정할 수 있어서, 최악에도 줄일 수 있음
        gt_pool: List[Tuple[str, str, Fraction]] = []
        for gt in ALL_GT:
            gt_pool.append(("GT", gt, dist.get(gt, Fraction(0))))

        # PH 조건: 8개(최대) 전부
        ph = ph_dist(dist)
        ph_pool: List[Tuple[str, str, Fraction]] = []
        for lab, pr in ph.items():
            ph_pool.append(("PH", lab, pr))

        # ✅ 조건 풀 우선순위:
        # - PH 중 0/1 아닌 것 우선(정보량 큼)
        # - GT 중 0/1 아닌 것 우선
        # - 그 다음 나머지
        ph_hi = [c for c in ph_pool if not is_low_info_prob(c[2])]
        ph_lo = [c for c in ph_pool if is_low_info_prob(c[2])]
        gt_hi = [c for c in gt_pool if not is_low_info_prob(c[2])]
        gt_lo = [c for c in gt_pool if is_low_info_prob(c[2])]

        # 풀 합치기(우선순위 반영)
        cond_pool = ph_hi + gt_hi + ph_lo + gt_lo

        chosen: List[Tuple[str, str, Fraction]] = []

        # 그리디 선택 루프
        while len(cand_idx) > 3 and len(chosen) < MAX_CONDS:
            # 이미 쓴 조건은 풀에서 제거
            remaining = [c for c in cond_pool if c not in chosen]
            best = pick_best_cond(cand_idx, case, remaining)
            if best is None:
                break
            chosen.append(best)
            cand_idx = filter_candidates(cand_idx, case, best)

            # 더 이상 안 줄어들면 탈출(다른 seed로)
            if len(cand_idx) > 3 and len(chosen) >= 6:
                # 너무 오래 걸리면 다른 seed로 넘어가게 안전장치
                pass

        if not (1 <= len(cand_idx) <= 3):
            continue

        # 최종 솔루션(≤3개)
        final_sols = [(case.pairs[i].idx1, case.pairs[i].idx2) for i in cand_idx]
        final_conds = chosen

        # ---------- 문제 텍스트 ----------
        problem_code = f"M3-{random.randint(1,999):03d}"
        pid = ID_PREFIX + sha10(f"{time.time()}_{problem_code}_{random.random()}")

        lg = list(linked)
        link_desc = f"({lg[0]}/{lg[0].lower()}), ({lg[1]}/{lg[1].lower()})는 연관이며 교차 없음(완전연관). 나머지 1쌍은 독립이다."

        ph_desc = (
            "※ 표현형은 **대문자 개수(k)**가 아니라, 각 유전자의 **우성 표현 여부(A+/B+/D+)**로 구분한다.\n"
            "- A형질: A가 하나라도 있으면(A+) 발현(A+), aa이면 비발현(A-)\n"
            "- B형질: B가 하나라도 있으면(B+) 발현(B+), bb이면 비발현(B-)\n"
            "- D형질: D가 하나라도 있으면(D+) 발현(D+), dd이면 비발현(D-)\n"
            "따라서 표현형은 (A+/A-, B+/B-, D+/D-) 형태로 나타난다.\n"
        )

        cond_lines = []
        for typ, key, pr in final_conds:
            if typ == "GT":
                cond_lines.append(f"- 자손 유전자형 **{key}** 의 확률 = **{frac_to_str(pr)}**")
            else:
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

        # ---------- 정답 ----------
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
            "- 같은 표현형 종류 수(ph_count)를 만족하는 모든 (P1,P2) 후보에서 시작해,\n"
            "- 후보를 가장 많이 줄이는 조건(유전자형/표현형 확률 조건)을 그리디로 순차 선택하여\n"
            "  정답 후보가 1~3개가 되도록 구성했다.\n"
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
                    {"type": typ, "key": key, "prob": frac_to_str(pr)}
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

    raise RuntimeError("문제 생성 실패: 조건 완화 필요 (seed/tries 증가 또는 MAX_CONDS 증가)")

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
