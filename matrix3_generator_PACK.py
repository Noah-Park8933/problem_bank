# matrix3_generator_PACK.py
# Matrix3 (일반유전) 문제 자동생성 + 유일정답 솔버 + PACK JSON 저장
# - (A/a),(B/b),(D/d) : 모두 상염색체
# - 연관 패턴: (2연관+1독립) 또는 (3연관)만 사용 (3독립 제거)
# - 완전연관(교차 없음) 고정
# - 표현형: A/B/D 각각 "우성 발현 여부" 조합 (대문자 개수 아님)
# - 제시조건: (표현형 종류 수) + (임의 유전자형 2개에 대한 확률 2개)
#   (0이다 조건 제거)

import os, json, time, random, hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Tuple, Optional, Any

# -----------------------------
# 기본 설정
# -----------------------------
MODULE = "MATRIX3"
ID_PREFIX = "MAT3_"
OUT_DIR = os.path.join(os.path.dirname(__file__), "output_pack")
os.makedirs(OUT_DIR, exist_ok=True)

RANDOM_SEED = None  # 필요하면 정수 넣기
if RANDOM_SEED is not None:
    random.seed(RANDOM_SEED)

# -----------------------------
# 확률 후보군 (요청 반영)
# 16계열: 1/16, 3/16
#  8계열: 1/8,  3/8
#  4계열: 1/4,  3/4
#  2계열: 1/2
# -----------------------------
PROB_POOL = [
    Fraction(1, 16), Fraction(3, 16),
    Fraction(1, 8),  Fraction(3, 8),
    Fraction(1, 4),  Fraction(3, 4),
    Fraction(1, 2),  Fraction(9, 16)
]

# -----------------------------
# 유틸
# -----------------------------
def frac_to_str(x: Fraction) -> str:
    if x.denominator == 1:
        return str(x.numerator)
    return f"{x.numerator}/{x.denominator}"

def sha10(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]

def combine_alleles(a: str, b: str) -> str:
    # 예: 'A' + 'a' => 'Aa' (대문자 우선 정렬)
    return "".join(sorted([a, b], key=lambda c: (c.islower(), c)))

def is_dom(geno2: str, gene: str) -> int:
    # gene='A'면 "AA"/"Aa" => 1, "aa" => 0
    return 1 if gene in geno2 else 0

def phenotype_label(A2: str, B2: str, D2: str) -> str:
    a = "A+" if is_dom(A2, "A") else "A-"
    b = "B+" if is_dom(B2, "B") else "B-"
    d = "D+" if is_dom(D2, "D") else "D-"
    return f"({a},{b},{d})"

# -----------------------------
# 유전자형 공간
# -----------------------------
G1 = ["AA", "Aa", "aa"]  # 단일 유전자형
ALL_GTS_27 = [a + b + d for a in G1 for b in G1 for d in G1]  # 27개

# -----------------------------
# 완전연관(교차 없음)에서 위상(하플로타입쌍) 생성
# -----------------------------
def possible_phases_2(gX: str, gY: str) -> List[Tuple[str, str]]:
    """
    두 유전자(예: A,B)의 유전자형(gX, gY)에 대해 가능한 하플로타입쌍(길이2) 반환.
    예: AaBb -> ("AB","ab") 또는 ("Ab","aB")
    반환은 (h1,h2) 정렬된 튜플.
    """
    X = [gX[0], gX[1]]
    Y = [gY[0], gY[1]]

    phases = set()

    h1 = X[0] + Y[0]
    h2 = X[1] + Y[1]
    if sorted([h1[0], h2[0]]) == sorted(X) and sorted([h1[1], h2[1]]) == sorted(Y):
        phases.add(tuple(sorted([h1, h2])))

    h1 = X[0] + Y[1]
    h2 = X[1] + Y[0]
    if sorted([h1[0], h2[0]]) == sorted(X) and sorted([h1[1], h2[1]]) == sorted(Y):
        phases.add(tuple(sorted([h1, h2])))

    return list(phases)

def possible_phases_3(gA: str, gB: str, gD: str) -> List[Tuple[str, str]]:
    """
    세 유전자 A,B,D 완전연관에서 가능한 하플로타입쌍(길이3) 반환.
    반환은 (h1,h2) 정렬된 튜플.
    """
    A = [gA[0], gA[1]]
    B = [gB[0], gB[1]]
    D = [gD[0], gD[1]]

    phases = set()
    for i in [0, 1]:
        for j in [0, 1]:
            for k in [0, 1]:
                h1 = A[i] + B[j] + D[k]
                h2 = A[1 - i] + B[1 - j] + D[1 - k]
                if sorted([h1[0], h2[0]]) != sorted(A):
                    continue
                if sorted([h1[1], h2[1]]) != sorted(B):
                    continue
                if sorted([h1[2], h2[2]]) != sorted(D):
                    continue
                phases.add(tuple(sorted([h1, h2])))
    return list(phases)

def gametes_from_phase(h1: str, h2: str) -> Dict[str, Fraction]:
    # 완전연관(교차 없음): h1/h2 => 생식세포는 각 1/2 (동형이면 1)
    if h1 == h2:
        return {h1: Fraction(1, 1)}
    return {h1: Fraction(1, 2), h2: Fraction(1, 2)}

def gametes_single(g: str) -> Dict[str, Fraction]:
    # 단일 유전자 생식세포: AA -> A, Aa -> A/a, aa -> a
    a1, a2 = g[0], g[1]
    if a1 == a2:
        return {a1: Fraction(1, 1)}
    return {a1: Fraction(1, 2), a2: Fraction(1, 2)}

# -----------------------------
# 부모 -> 자손 유전자형 분포 계산
# -----------------------------
def offspring_distribution(pattern: str, linked_genes: Tuple[str, ...], P1: Dict[str, Any], P2: Dict[str, Any]) -> Dict[str, Fraction]:
    """
    반환 key: "AABBdd" 같은 6글자 유전자형(각 gene 2글자)
    """
    def parent_gametes(P: Dict[str, Any]) -> Dict[Tuple[str, str, str], Fraction]:
        gA, gB, gD = P["gA"], P["gB"], P["gD"]

        if pattern == "L2I1":
            # 2 linked + 1 independent
            if set(linked_genes) == set(["A", "B"]):
                h1, h2 = P["phase2"]  # "AB" 형태
                g_link = gametes_from_phase(h1, h2)
                g_ind = gametes_single(gD)
                out: Dict[Tuple[str, str, str], Fraction] = {}
                for h, ph in g_link.items():
                    for d_allele, pd in g_ind.items():
                        out[(h[0], h[1], d_allele)] = out.get((h[0], h[1], d_allele), Fraction(0, 1)) + ph * pd
                return out

            if set(linked_genes) == set(["A", "D"]):
                h1, h2 = P["phase2"]  # "AD"
                g_link = gametes_from_phase(h1, h2)
                g_ind = gametes_single(gB)
                out: Dict[Tuple[str, str, str], Fraction] = {}
                for h, ph in g_link.items():
                    for b_allele, pb in g_ind.items():
                        out[(h[0], b_allele, h[1])] = out.get((h[0], b_allele, h[1]), Fraction(0, 1)) + ph * pb
                return out

            if set(linked_genes) == set(["B", "D"]):
                h1, h2 = P["phase2"]  # "BD"
                g_link = gametes_from_phase(h1, h2)
                g_ind = gametes_single(gA)
                out: Dict[Tuple[str, str, str], Fraction] = {}
                for h, ph in g_link.items():
                    for a_allele, pa in g_ind.items():
                        out[(a_allele, h[0], h[1])] = out.get((a_allele, h[0], h[1]), Fraction(0, 1)) + ph * pa
                return out

            raise RuntimeError("invalid linked_genes for L2I1")

        elif pattern == "L3":
            # 3 linked
            h1, h2 = P["phase3"]  # "ABD"
            g_link = gametes_from_phase(h1, h2)
            out: Dict[Tuple[str, str, str], Fraction] = {}
            for h, ph in g_link.items():
                out[(h[0], h[1], h[2])] = out.get((h[0], h[1], h[2]), Fraction(0, 1)) + ph
            return out

        else:
            raise RuntimeError("pattern must be L2I1 or L3")

    g1 = parent_gametes(P1)
    g2 = parent_gametes(P2)

    dist: Dict[str, Fraction] = {}
    for (a1, b1, d1), p1 in g1.items():
        for (a2, b2, d2), p2 in g2.items():
            A2 = combine_alleles(a1, a2)
            B2 = combine_alleles(b1, b2)
            D2 = combine_alleles(d1, d2)
            gt = A2 + B2 + D2
            dist[gt] = dist.get(gt, Fraction(0, 1)) + p1 * p2

    # 정규화(혹시 모를 안전장치)
    s = sum(dist.values(), Fraction(0, 1))
    if s != 1 and s != 0:
        for k in list(dist.keys()):
            dist[k] = dist[k] / s
    return dist

def phenotype_distribution(dist: Dict[str, Fraction]) -> Dict[str, Fraction]:
    out: Dict[str, Fraction] = {}
    for gt, pr in dist.items():
        if pr == 0:
            continue
        A2, B2, D2 = gt[0:2], gt[2:4], gt[4:6]
        lab = phenotype_label(A2, B2, D2)
        out[lab] = out.get(lab, Fraction(0, 1)) + pr
    return out

# -----------------------------
# 후보 부모/위상 열거(브루트 솔버)
# -----------------------------
def enumerate_parents(pattern: str, linked_genes: Tuple[str, ...]) -> List[Dict[str, Any]]:
    parents: List[Dict[str, Any]] = []
    for gA in G1:
        for gB in G1:
            for gD in G1:
                if pattern == "L2I1":
                    if set(linked_genes) == set(["A", "B"]):
                        for ph in possible_phases_2(gA, gB):
                            parents.append({"gA": gA, "gB": gB, "gD": gD, "phase2": ph})
                    elif set(linked_genes) == set(["A", "D"]):
                        for ph in possible_phases_2(gA, gD):
                            parents.append({"gA": gA, "gB": gB, "gD": gD, "phase2": ph})
                    elif set(linked_genes) == set(["B", "D"]):
                        for ph in possible_phases_2(gB, gD):
                            parents.append({"gA": gA, "gB": gB, "gD": gD, "phase2": ph})
                    else:
                        raise RuntimeError("invalid linked_genes")
                else:
                    for ph in possible_phases_3(gA, gB, gD):
                        parents.append({"gA": gA, "gB": gB, "gD": gD, "phase3": ph})
    return parents

def parent_str(P: Dict[str, Any], pattern: str) -> str:
    g = P["gA"] + P["gB"] + P["gD"]
    if pattern == "L2I1":
        return f"{g}  (연관상:{'/'.join(P['phase2'])})"
    return f"{g}  (연관상:{'/'.join(P['phase3'])})"

# -----------------------------
# 문제 생성(유일정답 보장)
# -----------------------------
@dataclass
class Problem:
    pid: str
    payload: Dict[str, Any]

def build_one_unique(max_tries: int = 60000) -> Problem:
    patterns = ["L2I1", "L3"]
    linked_options_L2 = [("A", "B"), ("A", "D"), ("B", "D")]

    cache_candidates: Dict[Tuple[str, Tuple[str, ...]], List[Dict[str, Any]]] = {}

    for _ in range(max_tries):
        pattern = random.choice(patterns)
        if pattern == "L2I1":
            linked_genes = random.choice(linked_options_L2)
        else:
            linked_genes = ("A", "B", "D")

        key = (pattern, linked_genes)
        if key not in cache_candidates:
            cache_candidates[key] = enumerate_parents(pattern, linked_genes)
        candidates = cache_candidates[key]

        P1 = random.choice(candidates)
        P2 = random.choice(candidates)
        if P1 == P2:
            continue

        dist = offspring_distribution(pattern, linked_genes, P1, P2)
        phdist = phenotype_distribution(dist)
        ph_count = len(phdist)  # pr>0만 넣었으니 그대로

        # 표현형 종류 수 범위(너무 좁으면 생성 실패 빨리 남)
        if not (3 <= ph_count <= 6):
            continue

        # dist -> 확률별 genotype 묶기 (27공간 기준으로 0도 포함)
        by_prob: Dict[Fraction, List[str]] = {}
        for gt in ALL_GTS_27:
            pr = dist.get(gt, Fraction(0, 1))
            by_prob.setdefault(pr, []).append(gt)

        avail_probs = [p for p in PROB_POOL if p in by_prob and any(dist.get(gt, Fraction(0, 1)) == p for gt in by_prob[p])]
        # 실제로 dist에서 등장(>0)하는 확률만
        avail_probs = [p for p in avail_probs if p > 0 and p < 1]

        if len(avail_probs) < 2:
            continue

        tgt1_pr = random.choice(avail_probs)
        tgt2_pr = random.choice([p for p in avail_probs if p != tgt1_pr])

        tgt1_candidates = [gt for gt in by_prob[tgt1_pr] if dist.get(gt, Fraction(0, 1)) == tgt1_pr]
        tgt2_candidates = [gt for gt in by_prob[tgt2_pr] if dist.get(gt, Fraction(0, 1)) == tgt2_pr]
        if not tgt1_candidates or not tgt2_candidates:
            continue

        tgt1_gt = random.choice(tgt1_candidates)
        tgt2_gt = random.choice(tgt2_candidates)

        # 유일해 솔버: (pattern, linked_genes, ph_count, P(tgt1)=tgt1_pr, P(tgt2)=tgt2_pr) 만족 (P1,P2) 유일?
        sols: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for c1 in candidates:
            for c2 in candidates:
                d2 = offspring_distribution(pattern, linked_genes, c1, c2)
                ph2 = phenotype_distribution(d2)
                if len(ph2) != ph_count:
                    continue
                if d2.get(tgt1_gt, Fraction(0, 1)) != tgt1_pr:
                    continue
                if d2.get(tgt2_gt, Fraction(0, 1)) != tgt2_pr:
                    continue

                sols.append((c1, c2))
                if len(sols) > 1:
                    break
            if len(sols) > 1:
                break

        if len(sols) != 1:
            continue

        solP1, solP2 = sols[0]

        # 문제 텍스트
        if pattern == "L2I1":
            lg = linked_genes
            link_desc = (
                f"({lg[0]}/{lg[0].lower()}), ({lg[1]}/{lg[1].lower()})는 연관이며 "
                f"교차는 일어나지 않는다(완전 연관). 나머지 1쌍은 독립이다."
            )
        else:
            link_desc = "(A/a), (B/b), (D/d)는 모두 연관이며 교차는 일어나지 않는다(완전 연관)."

        ph_desc = (
            "※ 표현형은 **대문자 개수**가 아니라, 각 유전자의 **우성 형질 발현 여부**로 구분한다.\n"
            "- A형질: A-이면 발현, aa이면 비발현\n"
            "- B형질: B-이면 발현, bb이면 비발현\n"
            "- D형질: D-이면 발현, dd이면 비발현\n"
            "따라서 자손 표현형은 (A+/A-, B+/B-, D+/D-) 형태로 나타낸다."
        )

        problem_code = f"M3-{random.randint(1,999):03d}"
        pid = ID_PREFIX + sha10(f"{time.time()}_{problem_code}_{random.random()}")

        problem_text_md = (
            f"문제 제목 : Matrix3 일반유전 추론 ({problem_code})\n\n"
            f"(A/a), (B/b), (D/d) 3쌍의 유전자가 각각 서로 다른 형질을 결정한다고 하자(단일인자 일반유전).\n"
            f"{link_desc}\n\n"
            f"- 부모 P1, P2의 유전자형은 미지수이다.\n"
            f"- P1×P2에서 나오는 **자손의 표현형 종류 수는 {ph_count}가지**이다.\n"
            f"- 자손의 유전자형이 **{tgt1_gt}** 일 확률은 **{frac_to_str(tgt1_pr)}** 이다.\n"
            f"- 자손의 유전자형이 **{tgt2_gt}** 일 확률은 **{frac_to_str(tgt2_pr)}** 이다.\n\n"
            f"{ph_desc}\n"
        )

        ask_line_md = "P1, P2의 유전자형(필요 시 연관 위상 포함)을 구하고, 자손 표현형의 종류와 각 확률을 구하시오."

        sol_dist = offspring_distribution(pattern, linked_genes, solP1, solP2)
        sol_ph = phenotype_distribution(sol_dist)

        ph_lines = []
        for k in sorted(sol_ph.keys()):
            ph_lines.append(f"- {k} : {frac_to_str(sol_ph[k])}")

        answer_text_md = (
            f"- P1 = {parent_str(solP1, pattern)}\n"
            f"- P2 = {parent_str(solP2, pattern)}\n\n"
            "자손 표현형 분포:\n" + "\n".join(ph_lines)
        )

        solution_md = (
            "### 해설(자동)\n"
            f"1) 연관/독립 조건은 문제에서 주어짐.\n"
            f"2) 제시된 '표현형 종류 수 = {ph_count}' 조건과 두 개의 유전자형 확률 조건을 만족하는 (P1,P2) 조합을 **전수검사**하여 유일해를 보장했다.\n"
            f"3) 본 문제의 표현형은 대문자 개수(k)가 아니라 (A형질, B형질, D형질)의 발현 여부 조합이다.\n"
            f"4) 최종적으로 P1×P2에서 나온 자손 유전자형 분포를 표현형 규칙(A-,B-,D-)에 따라 합산해 위의 표현형 확률을 얻는다.\n"
        )

        payload = {
            "module": MODULE,
            "id_prefix": ID_PREFIX,
            "problem_code": problem_code,
            "pattern": pattern,
            "linked_genes": list(linked_genes),
            "no_crossover": True,
            "constraints": {
                "phenotype_count": ph_count,
                "target1": {"genotype": tgt1_gt, "prob": frac_to_str(tgt1_pr)},
                "target2": {"genotype": tgt2_gt, "prob": frac_to_str(tgt2_pr)},
            },
            "P1": {
                "genotype": solP1["gA"] + solP1["gB"] + solP1["gD"],
                "phase": "/".join(solP1["phase2"]) if pattern == "L2I1" else "/".join(solP1["phase3"]),
            },
            "P2": {
                "genotype": solP2["gA"] + solP2["gB"] + solP2["gD"],
                "phase": "/".join(solP2["phase2"]) if pattern == "L2I1" else "/".join(solP2["phase3"]),
            },
            "problem_text_md": problem_text_md,
            "ask_line_md": ask_line_md,
            "answer_text_md": answer_text_md,
            "solution_md": solution_md,
            "difficulty": 2,
        }

        return Problem(pid=pid, payload=payload)

    raise RuntimeError("유일정답 Matrix3 문제 생성 실패: max_tries 증가 또는 조건 범위 완화 필요")

# -----------------------------
# PACK 저장
# -----------------------------
def make_pack(n: int = 30) -> str:
    items = []
    for i in range(1, n + 1):
        pr = build_one_unique(max_tries=60000)
        items.append({
            "id": pr.pid,
            "pid": pr.pid,
            "module": MODULE,
            "id_prefix": ID_PREFIX,
            "difficulty": pr.payload.get("difficulty", 2),
            "problem_text_md": pr.payload.get("problem_text_md", ""),
            "ask_line_md": pr.payload.get("ask_line_md", ""),
            "answer_text_md": pr.payload.get("answer_text_md", ""),
            "solution_md": pr.payload.get("solution_md", ""),
            "payload": pr.payload,
            "_qnum": i
        })

    pack = {
        "module": MODULE,
        "id_prefix": ID_PREFIX,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "items": items,
    }

    out_path = os.path.join(OUT_DIR, f"pack_{MODULE}_{int(time.time())}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)
    return out_path

if __name__ == "__main__":
    path = make_pack(n=30)
    print("[OK] PACK saved:", path)