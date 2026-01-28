# matrix3_generator_PACK.py
# Matrix3 (일반유전) – L2I1(2연관+1독립) 전용 / 완전연관(교차 없음)
# ✅ 파일 전체 교체용 (생성 실패 거의 0에 수렴하는 "seed+사전계산" 방식)
# ✅ 정답 후보는 최대 3개(>3이면 조건을 자동으로 추가해 줄임)
# ✅ pack 30개 안정 생성 목표

import os, json, time, random, hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Tuple, Any, Optional

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

# ----------------------------
# 위상(phase) 생성
# ----------------------------

def phases2(gX: str, gY: str) -> List[Tuple[str, str]]:
    """
    gX, gY는 각각 2글자(예: 'Aa', 'bb').
    반환: 가능한 완전연관 haplotype pair (h1, h2)들의 리스트.
          h1/h2는 2글자(각 유전자에서 1글자씩).
    """
    x = [gX[0], gX[1]]
    y = [gY[0], gY[1]]
    out = set()

    # coupling: x0-y0 / x1-y1
    h1 = x[0] + y[0]
    h2 = x[1] + y[1]
    if sorted([h1[0], h2[0]]) == sorted(x) and sorted([h1[1], h2[1]]) == sorted(y):
        out.add(tuple(sorted([h1, h2])))

    # repulsion: x0-y1 / x1-y0
    h1 = x[0] + y[1]
    h2 = x[1] + y[0]
    if sorted([h1[0], h2[0]]) == sorted(x) and sorted([h1[1], h2[1]]) == sorted(y):
        out.add(tuple(sorted([h1, h2])))

    return list(out)

def gam_phase(h1: str, h2: str) -> Dict[str, Fraction]:
    # 완전연관(교차 없음)에서 haplotype 두 개가 1:1
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
    """
    linked: ('A','B') or ('A','D') or ('B','D')
    P: {gA,gB,gD, phase2=(h1,h2)}  (phase2는 linked 두 유전자의 haplotype pair)
    """
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
                    # h[0]=A, h[1]=D
                    out[(h[0], b, h[1])] = out.get((h[0], b, h[1]), Fraction(0)) + ph * pb
            return out

        if set(linked) == {"B", "D"}:
            ga = gam_single(gA)
            out: Dict[Tuple[str, str, str], Fraction] = {}
            for h, ph in gp.items():
                for a, pa in ga.items():
                    # h[0]=B, h[1]=D
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
    # phase2는 linked된 두 유전자에 대한 haplotype pair(2글자/2글자)
    return f"{g} (연관상:{P['phase2'][0]}/{P['phase2'][1]})"

# ----------------------------
# 사전계산 + seed 만들기
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
    seeds: List[int]  # pairs 인덱스 목록(좋은 seed들)

def build_case_cache(linked: Tuple[str, str]) -> CaseCache:
    cands = enum_parents_L2I1(linked)
    pairs: List[PairInfo] = []

    # ordered pairs(순서 구분)로 저장: 해 후보가 대칭으로 늘어나는 문제를 줄이려면 여기서 (i<=j)로 줄여도 되는데,
    # 우리는 "조건으로 해를 줄이는" 방식이므로 ordered를 유지해도 OK.
    for i in range(len(cands)):
        for j in range(len(cands)):
            d = offspring_L2I1(linked, cands[i], cands[j])
            pc = ph_count_of_dist(d)
            pairs.append(PairInfo(i, j, pc, d))

    # seed 기준: 생성이 쉬운 분포만 남긴다
    seeds: List[int] = []
    for k, p in enumerate(pairs):
        if not (3 <= p.ph_count <= 6):
            continue

        # 0 확률 genotype이 충분히 존재해야(불가능 조건 만들기 쉬움)
        zeros = 0
        for gt in ALL_GT:
            if p.dist.get(gt, Fraction(0)) == 0:
                zeros += 1
        if zeros < 4:
            continue

        # 양의 확률 genotype이 너무 적으면 조건 뽑아도 정보량이 부족
        pos = sum(1 for v in p.dist.values() if v > 0)
        if pos < 6:
            continue

        seeds.append(k)

    return CaseCache(linked=linked, cands=cands, pairs=pairs, seeds=seeds)

# ----------------------------
# 빠른 해 탐색(≤3 초과면 즉시 중단)
# ----------------------------

def count_solutions_upto3(case: CaseCache, ph_count: int, conds: List[Tuple[str, Fraction]]) -> List[Tuple[int, int]]:
    sols: List[Tuple[int, int]] = []
    for p in case.pairs:
        if p.ph_count != ph_count:
            continue
        ok = True
        d = p.dist
        for gt, pr in conds:
            if d.get(gt, Fraction(0)) != pr:
                ok = False
                break
        if ok:
            sols.append((p.idx1, p.idx2))
            if len(sols) > 3:
                return sols
    return sols

# ----------------------------
# 문제 생성(Guaranteed-style)
# ----------------------------

@dataclass
class Problem:
    pid: str
    payload: Dict[str, Any]

def build_one(case_caches: Dict[Tuple[str, str], CaseCache],
              max_seed_tries: int = 2000) -> Problem:

    lopts = [("A", "B"), ("A", "D"), ("B", "D")]

    # 보기 좋은 분수(있으면 우선 사용). 없으면 자동 폴백.
    pretty = {
        Fraction(1, 16), Fraction(3, 16),
        Fraction(1, 8),  Fraction(3, 8),
        Fraction(1, 4),  Fraction(3, 4),
        Fraction(1, 2),  Fraction(9, 16),
    }

    for _ in range(max_seed_tries):
        linked = random.choice(lopts)
        case = case_caches[linked]

        # seed가 비면(이론상 거의 없음) 다른 케이스로
        if not case.seeds:
            continue

        seed_idx = random.choice(case.seeds)
        seed = case.pairs[seed_idx]
        dist = seed.dist
        ph_count = seed.ph_count

        # 조건 후보 풀
        zeros = [gt for gt in ALL_GT if dist.get(gt, Fraction(0)) == 0]
        pos_all = [(gt, pr) for gt, pr in dist.items() if pr > 0]

        # pos 중 "예쁜 분수" 우선 (없으면 pos_all에서)
        pos_pretty = [(gt, pr) for gt, pr in pos_all if pr in pretty]
        if pos_pretty:
            random.shuffle(pos_pretty)
            pos_pool = pos_pretty + pos_all
        else:
            pos_pool = pos_all

        if not zeros or not pos_pool:
            continue

        # 1) 조건 2개로 시작: (양의 확률 1개) + (0 확률 1개)
        conds: List[Tuple[str, Fraction]] = []
        used_gts = set()

        gt1, pr1 = random.choice(pos_pool)
        conds.append((gt1, pr1)); used_gts.add(gt1)

        gt0 = random.choice(zeros)
        conds.append((gt0, Fraction(0))); used_gts.add(gt0)

        sols = count_solutions_upto3(case, ph_count, conds)

        if len(sols) == 0:
            continue
        if 1 <= len(sols) <= 3:
            final_conds = conds
            final_sols = sols
        else:
            # 2) 조건 3개로 강화
            extra_pos = [(gt, pr) for gt, pr in pos_pool if gt not in used_gts]
            if not extra_pos:
                continue
            gt2, pr2 = random.choice(extra_pos)
            conds3 = conds + [(gt2, pr2)]
            sols3 = count_solutions_upto3(case, ph_count, conds3)

            if len(sols3) == 0:
                continue
            if 1 <= len(sols3) <= 3:
                final_conds = conds3
                final_sols = sols3
            else:
                # 3) 조건 4개로 한 번 더 강화(거의 여기서 끝남)
                used2 = used_gts | {gt2}
                extra_pos2 = [(gt, pr) for gt, pr in pos_pool if gt not in used2]
                if not extra_pos2:
                    continue
                gt3, pr3 = random.choice(extra_pos2)
                conds4 = conds3 + [(gt3, pr3)]
                sols4 = count_solutions_upto3(case, ph_count, conds4)
                if not (1 <= len(sols4) <= 3):
                    continue
                final_conds = conds4
                final_sols = sols4

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
        for gt, pr in final_conds:
            if pr == 0:
                cond_lines.append(f"- 자손 유전자형 **{gt}** 의 확률 = **0**")
            else:
                cond_lines.append(f"- 자손 유전자형 **{gt}** 의 확률 = **{frac_to_str(pr)}**")

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
            "- 먼저 사전계산된 (P1,P2) 분포들 중 ‘조건으로 해를 잘 분리할 수 있는 seed’를 선택한다.\n"
            "- seed 분포에서 (가능한 유전자형 1개 + 불가능(0) 유전자형 1개) 조건을 만들고,\n"
            "  정답 후보가 3개를 초과하면 유전자형 확률 조건을 1~2개 추가하여 1~3개로 줄인다.\n"
        )

        payload = {
            "module": MODULE,
            "id_prefix": ID_PREFIX,
            "problem_code": problem_code,
            "pattern": "L2I1",
            "linked_genes": list(linked),
            "constraints": {
                "phenotype_count": ph_count,
                "conditions": [{"genotype": gt, "prob": ("0" if pr == 0 else frac_to_str(pr))} for gt, pr in final_conds],
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

    raise RuntimeError("문제 생성 실패: 조건 완화 필요 (seed에서 유효 조건을 못 찾음)")

# ----------------------------
# PACK 저장
# ----------------------------

def make_pack(n: int = 30) -> str:
    # ✅ 케이스 캐시는 프로그램 실행 중 1회만 생성
    case_caches: Dict[Tuple[str, str], CaseCache] = {}
    for linked in [("A", "B"), ("A", "D"), ("B", "D")]:
        case_caches[linked] = build_case_cache(linked)
        # 디버그용(원하면 주석 해제)
        # print("[cache]", linked, "cands=", len(case_caches[linked].cands),
        #       "pairs=", len(case_caches[linked].pairs),
        #       "seeds=", len(case_caches[linked].seeds))

    items: List[Dict[str, Any]] = []
    for i in range(1, n + 1):
        pr = build_one(case_caches)
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
