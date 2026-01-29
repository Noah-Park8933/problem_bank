# matrix4_generator_PACK.py
# Matrix4 (일반유전) – 고정 구조:
# ✅ (A/a)-(B/b) 완전연관(교차 없음)
# ✅ (D/d)-(E/e) 완전연관(교차 없음)
# ✅ 두 연관군(AB)와 (DE)는 서로 독립
#
# 생성 실패 방지(핵심):
# 1) 자손 조건(유전자형/표현형 확률)로 후보를 먼저 줄이고
# 2) 그래도 해(정답 후보)가 3개 초과면 "부모 조건(부모 표현형/부모 좌위 유전자형)"을 자동 추가해서 ≤3으로 강제
#
# 성능 최적화(중요):
# - 완전연관이라 확률 분모는 최대 16이므로, Fraction 대신 "16분율 카운트(int 0..16)"로 dist를 저장
# - 부모 gamete 분모는 4이므로 "4분율 카운트(int 0..4)"로 처리 → 교배 후 16분율로 누적

import os, json, time, random, hashlib
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

MODULE = "MATRIX4"
ID_PREFIX = "MAT4_"
OUT_DIR = os.path.join(os.path.dirname(__file__), "output_pack")
os.makedirs(OUT_DIR, exist_ok=True)

# 고정: AB 연관, DE 연관, 두 군은 독립
LINK1 = ("A", "B")
LINK2 = ("D", "E")

# ----------------------------
# 기본 유틸
# ----------------------------

def sha10(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:10]

def combine(a: str, b: str) -> str:
    # 대문자 우선 + 알파벳 기준
    return "".join(sorted([a, b], key=lambda c: (c.islower(), c)))

def is_dom(geno2: str, allele: str) -> int:
    return 1 if allele in geno2 else 0

def frac16_to_str(k: int) -> str:
    # k/16 간단화 출력
    if k == 0:
        return "0"
    if k == 16:
        return "1"
    # 약분
    import math
    g = math.gcd(k, 16)
    return f"{k//g}/{16//g}"

def ph_label4(gt: str) -> str:
    # gt: A2(2)+B2(2)+D2(2)+E2(2)=8
    A2, B2, D2, E2 = gt[0:2], gt[2:4], gt[4:6], gt[6:8]
    return f"({ 'A+' if is_dom(A2,'A') else 'A-' },{ 'B+' if is_dom(B2,'B') else 'B-' },{ 'D+' if is_dom(D2,'D') else 'D-' },{ 'E+' if is_dom(E2,'E') else 'E-' })"

# 4좌위 전체 유전자형(3^4=81)
A_SET = ["AA","Aa","aa"]
B_SET = ["BB","Bb","bb"]
D_SET = ["DD","Dd","dd"]
E_SET = ["EE","Ee","ee"]

ALL_GT: List[str] = []
for A2 in A_SET:
    for B2 in B_SET:
        for D2 in D_SET:
            for E2 in E_SET:
                ALL_GT.append(A2+B2+D2+E2)

GT_INDEX = {gt:i for i,gt in enumerate(ALL_GT)}  # length 81

# ----------------------------
# phase(연관상) 생성
# ----------------------------

def phases2(gX: str, gY: str) -> List[Tuple[str, str]]:
    # gX="Aa", gY="Bb" → haplotype pair like ("AB","ab") etc
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

def gam_phase_counts(h1: str, h2: str) -> Dict[str, int]:
    # return haplotype->count out of 2
    if h1 == h2:
        return {h1: 2}
    return {h1: 1, h2: 1}

def gam_single_counts(g: str) -> Dict[str, int]:
    # allele -> count out of 2
    a1, a2 = g[0], g[1]
    if a1 == a2:
        return {a1: 2}
    return {a1: 1, a2: 1}

# ----------------------------
# 부모 후보 생성(AB phase + DE phase)
# ----------------------------

def enum_parents_ABDE() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for gA in A_SET:
        for gB in B_SET:
            for gD in D_SET:
                for gE in E_SET:
                    phAB = phases2(gA, gB)
                    phDE = phases2(gD, gE)
                    for pAB in phAB:
                        for pDE in phDE:
                            out.append({
                                "gA": gA, "gB": gB, "gD": gD, "gE": gE,
                                "phaseAB": pAB,  # (h1,h2) each 2 chars
                                "phaseDE": pDE,  # (h1,h2) each 2 chars
                            })
    return out

def pstr(P: Dict[str, Any]) -> str:
    g = P["gA"]+P["gB"]+P["gD"]+P["gE"]
    return f"{g} (AB:{P['phaseAB'][0]}/{P['phaseAB'][1]}, DE:{P['phaseDE'][0]}/{P['phaseDE'][1]})"

def parent_ph(P: Dict[str, Any]) -> str:
    A = "A+" if ("A" in P["gA"]) else "A-"
    B = "B+" if ("B" in P["gB"]) else "B-"
    D = "D+" if ("D" in P["gD"]) else "D-"
    E = "E+" if ("E" in P["gE"]) else "E-"
    return f"({A},{B},{D},{E})"

# ----------------------------
# 자손 분포 (16분율 카운트로 저장)
# ----------------------------

def parent_gametes_counts(P: Dict[str, Any]) -> Dict[Tuple[str,str,str,str], int]:
    """
    return gamete -> count out of 4
    gamete tuple: (Aallele, Ballele, Dallele, Eallele)
    AB haplotype counts out of 2, DE haplotype counts out of 2
    independent between groups → joint out of 4
    """
    (ab1, ab2) = P["phaseAB"]
    (de1, de2) = P["phaseDE"]
    gAB = gam_phase_counts(ab1, ab2)   # out of 2
    gDE = gam_phase_counts(de1, de2)   # out of 2

    out: Dict[Tuple[str,str,str,str], int] = {}
    for hab, cab in gAB.items():
        for hde, cde in gDE.items():
            # hab="Ab" => A allele hab[0], B allele hab[1]
            # hde="De" => D allele hde[0], E allele hde[1]
            gam = (hab[0], hab[1], hde[0], hde[1])
            out[gam] = out.get(gam, 0) + cab * cde  # out of 4
    return out

def offspring_dist16(P1: Dict[str, Any], P2: Dict[str, Any]) -> List[int]:
    """
    return counts list length 81, each int 0..16 representing probability = k/16
    """
    g1 = parent_gametes_counts(P1)  # out of 4
    g2 = parent_gametes_counts(P2)  # out of 4
    counts = [0]*len(ALL_GT)        # out of 16

    for (a1,b1,d1,e1), w1 in g1.items():  # w1 out of 4
        for (a2,b2,d2,e2), w2 in g2.items():  # w2 out of 4
            A2 = combine(a1, a2)
            B2 = combine(b1, b2)
            D2 = combine(d1, d2)
            E2 = combine(e1, e2)
            gt = A2+B2+D2+E2
            counts[GT_INDEX[gt]] += w1*w2  # out of 16
    return counts

def ph_dist16(counts: List[int]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for gt, idx in GT_INDEX.items():
        k = counts[idx]
        if k == 0:
            continue
        lab = ph_label4(gt)
        out[lab] = out.get(lab, 0) + k
    return out

def ph_count_of_counts(counts: List[int]) -> int:
    pd = ph_dist16(counts)
    return sum(1 for v in pd.values() if v > 0)

# ----------------------------
# 사전계산 Pair 테이블 (unordered)
# ----------------------------

@dataclass(frozen=True)
class PairInfo:
    idx1: int
    idx2: int
    ph_count: int
    counts: Tuple[int, ...]  # length 81, each 0..16

@dataclass
class Cache:
    cands: List[Dict[str, Any]]
    pairs: List[PairInfo]

def build_cache() -> Cache:
    cands = enum_parents_ABDE()
    pairs: List[PairInfo] = []
    for i in range(len(cands)):
        for j in range(i, len(cands)):
            cnt = offspring_dist16(cands[i], cands[j])
            pc = ph_count_of_counts(cnt)
            pairs.append(PairInfo(i, j, pc, tuple(cnt)))
    return Cache(cands=cands, pairs=pairs)

# ----------------------------
# 후보 필터링
# ----------------------------

def filter_pairs_by_child_conds(cache: Cache, ph_count: int, child_conds: List[Tuple[str, str, int]]) -> List[int]:
    """
    child_conds:
      - ("GT", genotype, k16)
      - ("PH", phenotype_label, k16)
    반환: cache.pairs 인덱스 리스트
    """
    out: List[int] = []
    for pidx, p in enumerate(cache.pairs):
        if p.ph_count != ph_count:
            continue
        ok = True
        ph_cache = None
        for typ, key, k16 in child_conds:
            if typ == "GT":
                if p.counts[GT_INDEX[key]] != k16:
                    ok = False
                    break
            else:  # PH
                if ph_cache is None:
                    ph_cache = ph_dist16(list(p.counts))
                if ph_cache.get(key, 0) != k16:
                    ok = False
                    break
        if ok:
            out.append(pidx)
    return out

def filter_by_parent_constraint(cache: Cache, cand_pair_idxs: List[int], constraint: Tuple[str, int, str]) -> List[int]:
    """
    constraint: (kind, who, value)
    kind: "PH" or "GA"/"GB"/"GD"/"GE"
    who: 1 or 2
    """
    kind, who, value = constraint
    out: List[int] = []
    for pidx in cand_pair_idxs:
        p = cache.pairs[pidx]
        P = cache.cands[p.idx1] if who == 1 else cache.cands[p.idx2]
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
        elif kind == "GE":
            if P["gE"] == value:
                out.append(pidx)
    return out

# ----------------------------
# 문제 생성
# ----------------------------

@dataclass
class Problem:
    pid: str
    payload: Dict[str, Any]

def build_one(cache: Cache, max_seed_tries: int = 3000) -> Problem:
    for _ in range(max_seed_tries):
        seed = random.choice(cache.pairs)
        ph_count = seed.ph_count
        if not (5 <= ph_count <= 12):  # 4유전자라 너무 단순한 케이스 방지
            continue

        seed_counts = list(seed.counts)
        # 자손 조건 풀(Seed의 "진짜 값" 기반)
        gt_pool = [("GT", gt, seed_counts[GT_INDEX[gt]]) for gt in ALL_GT]
        ph_seed = ph_dist16(seed_counts)
        ph_pool = [("PH", lab, k16) for lab, k16 in ph_seed.items() if k16 > 0]

        def info_score(k16: int) -> int:
            return 0 if (k16 != 0 and k16 != 16) else 1  # 0/1은 정보 낮음

        gt_pool.sort(key=lambda x: info_score(x[2]))
        ph_pool.sort(key=lambda x: info_score(x[2]))
        child_pool = ph_pool + gt_pool  # PH 먼저

        # 같은 ph_count 후보로 시작
        cand_idxs = [i for i, p in enumerate(cache.pairs) if p.ph_count == ph_count]
        if not cand_idxs:
            continue

        # 자손 조건 그리디(최대 10개)
        child_conds: List[Tuple[str, str, int]] = []
        for _k in range(10):
            if len(cand_idxs) <= 3:
                break
            best = None
            best_size = None
            for cond in child_pool:
                if cond in child_conds:
                    continue
                filtered = filter_pairs_by_child_conds(cache, ph_count, child_conds + [cond])
                if not filtered:
                    continue
                s = len(filtered)
                if best is None or s < best_size:
                    best = cond
                    best_size = s
                    if s <= 3:
                        break
            if best is None:
                break
            child_conds.append(best)
            cand_idxs = filter_pairs_by_child_conds(cache, ph_count, child_conds)

        # 그래도 많으면 부모조건 자동 추가
        parent_constraints: List[Tuple[str, int, str]] = []
        if len(cand_idxs) > 3:
            pool: List[Tuple[str, int, str]] = []
            ph_vals = [
                "(A+,B+,D+,E+)", "(A+,B+,D+,E-)", "(A+,B+,D-,E+)", "(A+,B+,D-,E-)",
                "(A+,B-,D+,E+)", "(A+,B-,D+,E-)", "(A+,B-,D-,E+)", "(A+,B-,D-,E-)",
                "(A-,B+,D+,E+)", "(A-,B+,D+,E-)", "(A-,B+,D-,E+)", "(A-,B+,D-,E-)",
                "(A-,B-,D+,E+)", "(A-,B-,D+,E-)", "(A-,B-,D-,E+)", "(A-,B-,D-,E-)",
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
                for g in ["EE", "Ee", "ee"]:
                    pool.append(("GE", who, g))

            random.shuffle(pool)

            for c in pool:
                reduced = filter_by_parent_constraint(cache, cand_idxs, c)
                if not reduced:
                    continue
                if len(reduced) < len(cand_idxs):
                    parent_constraints.append(c)
                    cand_idxs = reduced
                if len(cand_idxs) <= 3:
                    break

        if not (1 <= len(cand_idxs) <= 3):
            continue

        final_sols = [(cache.pairs[i].idx1, cache.pairs[i].idx2) for i in cand_idxs]

        # ---------- 문제 텍스트 ----------
        problem_code = f"M4-ABDE-{random.randint(1,999):03d}"
        pid = ID_PREFIX + sha10(f"{time.time()}_{problem_code}_{random.random()}")

        link_desc = (
            "(A/a)와 (B/b)는 연관이며 교차 없음(완전연관), (D/d)와 (E/e)도 연관이며 교차 없음(완전연관)이다.\n"
            "두 연관군 (AB)와 (DE)는 서로 독립이다."
        )

        ph_desc = (
            "※ 표현형은 **각 유전자의 우성 발현 여부(A+/B+/D+/E+)**로 구분한다.\n"
            "- A 유전자에 'A'가 1개 이상 있으면(Aa, AA) 발현(A+), 없으면(aa) 비발현(A-)\n"
            "- B 유전자에 'B'가 1개 이상 있으면(Bb, BB) 발현(B+), 없으면(bb) 비발현(B-)\n"
            "- D 유전자에 'D'가 1개 이상 있으면(Dd, DD) 발현(D+), 없으면(dd) 비발현(D-)\n"
            "- E 유전자에 'E'가 1개 이상 있으면(Ee, EE) 발현(E+), 없으면(ee) 비발현(E-)\n"
            "따라서 표현형은 (A+/A-, B+/B-, D+/D-, E+/E-) 형태로 나타난다.\n"
        )

        cond_lines = []
        for typ, key, k16 in child_conds:
            if typ == "GT":
                cond_lines.append(f"- 자손 유전자형 **{key}** 의 확률 = **{frac16_to_str(k16)}**")
            else:
                cond_lines.append(f"- 자손 표현형 **{key}** 의 확률 = **{frac16_to_str(k16)}**")

        for kind, who, val in parent_constraints:
            if kind == "PH":
                cond_lines.append(f"- 부모 P{who}의 표현형은 **{val}** 이다.")
            elif kind == "GA":
                cond_lines.append(f"- 부모 P{who}의 A좌위 유전자형은 **{val}** 이다.")
            elif kind == "GB":
                cond_lines.append(f"- 부모 P{who}의 B좌위 유전자형은 **{val}** 이다.")
            elif kind == "GD":
                cond_lines.append(f"- 부모 P{who}의 D좌위 유전자형은 **{val}** 이다.")
            elif kind == "GE":
                cond_lines.append(f"- 부모 P{who}의 E좌위 유전자형은 **{val}** 이다.")

        problem_text_md = (
            f"문제 제목 : Matrix4 일반유전 추론 (AB연관 + DE연관) ({problem_code})\n\n"
            f"(A/a), (B/b), (D/d), (E/e) 네 유전자는 각각 다른 형질을 결정한다(일반유전).\n"
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
            c1 = cache.cands[i1]
            c2 = cache.cands[i2]
            answer_lines.append(f"[후보 {idx_s}]")
            answer_lines.append(f"- P1 = {pstr(c1)}")
            answer_lines.append(f"- P2 = {pstr(c2)}")

            cnt = offspring_dist16(c1, c2)
            phsol = ph_dist16(cnt)
            for k in sorted(phsol.keys()):
                if phsol[k] > 0:
                    answer_lines.append(f"  - {k} : {frac16_to_str(phsol[k])}")
            answer_lines.append("")

        answer_text_md = "\n".join(answer_lines)

        solution_md = (
            "### 해설(자동)\n"
            "- AB 완전연관, DE 완전연관, 두 연관군 독립에서 자손(유전자형/표현형 확률) 조건으로 후보를 줄인다.\n"
            "- 완전연관 구조에서는 동치해가 남을 수 있어, 필요 시 부모 표현형/부모 좌위 유전자형 조건을 자동 추가하여 정답 후보를 1~3개로 만든다.\n"
        )

        payload = {
            "module": MODULE,
            "id_prefix": ID_PREFIX,
            "problem_code": problem_code,
            "pattern": "AB_linked__DE_linked__groups_independent",
            "constraints": {
                "phenotype_count": ph_count,
                "child_conditions": [{"type": typ, "key": key, "prob": frac16_to_str(k16)} for (typ, key, k16) in child_conds],
                "parent_conditions": [{"kind": k, "who": w, "value": v} for (k, w, v) in parent_constraints],
            },
            "solutions": [
                {"P1": pstr(cache.cands[i1]), "P2": pstr(cache.cands[i2])}
                for (i1, i2) in final_sols
            ],
            "problem_text_md": problem_text_md,
            "ask_line_md": ask_line_md,
            "answer_text_md": answer_text_md,
            "solution_md": solution_md,
        }

        return Problem(pid, payload)

    raise RuntimeError("문제 생성 실패: tries 증가 필요")

# ----------------------------
# PACK 저장
# ----------------------------

def make_pack(n: int = 30) -> str:
    cache = build_cache()

    items: List[Dict[str, Any]] = []
    for i in range(1, n + 1):
        pr = build_one(cache, max_seed_tries=3000)
        items.append({
            "id": pr.pid,
            "pid": pr.pid,
            "module": MODULE,
            "id_prefix": ID_PREFIX,
            "difficulty": 3,
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
