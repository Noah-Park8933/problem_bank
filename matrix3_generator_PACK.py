# matrix3_generator_PACK.py
# Matrix3 (일반유전) – 복수 정답 허용 버전
# (A/a), (B/b), (D/d) / 완전연관 기반 / 2연관+1독립 또는 3연관
# 표현형: "대문자 개수"가 아니라 세 유전자의 "우성 발현 여부 조합"

import os, json, time, random, hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Tuple, Optional, Any

MODULE = "MATRIX3"
ID_PREFIX = "MAT3_"
OUT_DIR = os.path.join(os.path.dirname(__file__), "output_pack")
os.makedirs(OUT_DIR, exist_ok=True)

# ----------------------------
# 기본 함수들
# ----------------------------

def frac_to_str(fr: Fraction) -> str:
    if fr.denominator == 1:
        return str(fr.numerator)
    return f"{fr.numerator}/{fr.denominator}"

def sha10(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:10]

def is_dom(geno2: str, allele: str) -> int:
    return 1 if allele in geno2 else 0

def ph_label(gt: str) -> str:
    A2, B2, D2 = gt[0:2], gt[2:4], gt[4:6]
    return f"({ 'A+' if is_dom(A2,'A') else 'A-' },{ 'B+' if is_dom(B2,'B') else 'B-' },{ 'D+' if is_dom(D2,'D') else 'D-' })"

G1 = ["AA", "Aa", "aa"]

def combine(a, b):
    return "".join(sorted([a,b], key=lambda c:(c.islower(),c)))

def phases2(gX, gY):
    x = [gX[0], gX[1]]
    y = [gY[0], gY[1]]
    out=set()

    h1=x[0]+y[0]; h2=x[1]+y[1]
    if sorted([h1[0],h2[0]])==sorted(x) and sorted([h1[1],h2[1]])==sorted(y):
        out.add(tuple(sorted([h1,h2])))

    h1=x[0]+y[1]; h2=x[1]+y[0]
    if sorted([h1[0],h2[0]])==sorted(x) and sorted([h1[1],h2[1]])==sorted(y):
        out.add(tuple(sorted([h1,h2])))

    return list(out)

def phases3(gA, gB, gD):
    A=[gA[0],gA[1]]; B=[gB[0],gB[1]]; D=[gD[0],gD[1]]
    out=set()
    for i in [0,1]:
        for j in [0,1]:
            for k in [0,1]:
                h1 = A[i]+B[j]+D[k]
                h2 = A[1-i]+B[1-j]+D[1-k]
                if sorted([h1[0],h2[0]])!=sorted(A):continue
                if sorted([h1[1],h2[1]])!=sorted(B):continue
                if sorted([h1[2],h2[2]])!=sorted(D):continue
                out.add(tuple(sorted([h1,h2])))
    return list(out)

def gam_phase(h1,h2):
    if h1==h2: return {h1:Fraction(1)}
    return {h1:Fraction(1,2), h2:Fraction(1,2)}

def gam_single(g):
    a1,a2=g[0],g[1]
    if a1==a2: return {a1:Fraction(1)}
    return {a1:Fraction(1,2), a2:Fraction(1,2)}

# ----------------------------
# 자손 분포 계산
# ----------------------------

def offspring(pattern, linked, P1, P2):
    def gams(P):
        gA,gB,gD=P["gA"],P["gB"],P["gD"]
        if pattern=="L2I1":
            if set(linked)=={"A","B"}:
                h1,h2 = P["phase2"]
                gp=gam_phase(h1,h2)
                gd=gam_single(gD)
                out={}
                for h,ph in gp.items():
                    for d,pd in gd.items():
                        out[(h[0],h[1],d)] = out.get((h[0],h[1],d),Fraction(0))+ph*pd
                return out
            if set(linked)=={"A","D"}:
                h1,h2=P["phase2"]
                gp=gam_phase(h1,h2)
                gb=gam_single(gB)
                out={}
                for h,ph in gp.items():
                    for b,pb in gb.items():
                        out[(h[0],b,h[1])] = out.get((h[0],b,h[1]),Fraction(0))+ph*pb
                return out
            if set(linked)=={"B","D"}:
                h1,h2=P["phase2"]
                gp=gam_phase(h1,h2)
                ga=gam_single(gA)
                out={}
                for h,ph in gp.items():
                    for a,pa in ga.items():
                        out[(a,h[0],h[1])] = out.get((a,h[0],h[1]),Fraction(0))+ph*pa
                return out
            raise RuntimeError("invalid linked")
        else:
            # L3
            h1,h2=P["phase3"]
            gp=gam_phase(h1,h2)
            out={}
            for h,ph in gp.items():
                out[(h[0],h[1],h[2])] = out.get((h[0],h[1],h[2]),Fraction(0))+ph
            return out

    g1=gams(P1); g2=gams(P2)
    dist={}
    for (a1,b1,d1),p1 in g1.items():
        for (a2,b2,d2),p2 in g2.items():
            A2=combine(a1,a2)
            B2=combine(b1,b2)
            D2=combine(d1,d2)
            gt=A2+B2+D2
            dist[gt]=dist.get(gt,Fraction(0))+p1*p2

    # normalize
    s=sum(dist.values(),Fraction(0))
    if s!=1:
        for k in dist:
            dist[k]/=s
    return dist

def ph_dist(dist):
    out={}
    for gt,pr in dist.items():
        lab=ph_label(gt)
        out[lab]=out.get(lab,Fraction(0))+pr
    return out

# ----------------------------
# 모든 P1,P2 후보 생성
# ----------------------------

def enum_parents(pattern, linked):
    out=[]
    for gA in G1:
        for gB in G1:
            for gD in G1:
                if pattern=="L2I1":
                    if set(linked)=={"A","B"}:
                        phs=phases2(gA,gB)
                    elif set(linked)=={"A","D"}:
                        phs=phases2(gA,gD)
                    else:
                        phs=phases2(gB,gD)
                    for ph in phs:
                        out.append({"gA":gA,"gB":gB,"gD":gD,"phase2":ph})
                else:
                    phs=phases3(gA,gB,gD)
                    for ph in phs:
                        out.append({"gA":gA,"gB":gB,"gD":gD,"phase3":ph})
    return out

def pstr(P,pattern,linked):
    g=P["gA"]+P["gB"]+P["gD"]
    if pattern=="L2I1":
        return f"{g} (연관상:{P['phase2'][0]}/{P['phase2'][1]})"
    return f"{g} (연관상:{P['phase3'][0]}/{P['phase3'][1]})"

# ----------------------------
# 문제 생성 (복수정답)
# ----------------------------

@dataclass
class Problem:
    pid:str
    payload:Dict[str,Any]

def prepare_case_cache(pattern, linked):
    """
    (pattern, linked) 케이스에 대해:
    - 모든 부모 후보 cands
    - 모든 (P1,P2)쌍에 대한 dist/ph_count 미리 계산
    를 캐시로 만들어 반환.
    """
    cands = enum_parents(pattern, linked)

    pairs = []
    # (P1,P2) 전체쌍 사전 계산 (순서 구분: (c1,c2)와 (c2,c1) 둘 다 넣으면 해 탐색 쉬움)
    for c1 in cands:
        for c2 in cands:
            # 같은 부모 허용 여부는 여기서 조절 가능
            # if c1 == c2: continue  # 원하면 주석 해제/해제
            d = offspring(pattern, linked, c1, c2)
            ph = ph_dist(d)
            ph_count = sum(1 for v in ph.values() if v > 0)
            pairs.append({
                "P1": c1,
                "P2": c2,
                "dist": d,
                "ph_count": ph_count,
            })

    return {"cands": cands, "pairs": pairs}


def build_one(max_tries=30000):
    patterns = ["L2I1", "L3"]
    lopts = [("A","B"), ("A","D"), ("B","D")]

    allowed = [
        Fraction(1,16), Fraction(3,16),
        Fraction(1,8), Fraction(3,8),
        Fraction(1,4), Fraction(3,4),
        Fraction(1,2), Fraction(9,16)
    ]

    # 케이스별 캐시: (pattern, linked) -> {"cands":..., "pairs":...}
    case_cache = {}

    for _ in range(max_tries):
        pattern = random.choice(patterns)
        if pattern == "L2I1":
            linked = random.choice(lopts)
        else:
            linked = ("A","B","D")

        key = (pattern, linked)
        if key not in case_cache:
            case_cache[key] = prepare_case_cache(pattern, linked)

        pairs = case_cache[key]["pairs"]

        # 1) ph_count 조건(3~6) 만족하는 pair 중 하나 랜덤 선택
        filtered_pairs = [x for x in pairs if 3 <= x["ph_count"] <= 6]
        if not filtered_pairs:
            continue
        picked = random.choice(filtered_pairs)

        dist = picked["dist"]
        ph_count = picked["ph_count"]

        # 2) target1: allowed 확률에 해당하는 실제 존재 유전자형
        possibles = [(gt, pr) for gt, pr in dist.items() if pr in allowed]
        if not possibles:
            continue
        tgt1_gt, tgt1_pr = random.choice(possibles)

        # 3) target2: 확률 0인 유전자형(= 전체 27개 중 dist에 없거나 0인 것)
        zeros = [gt for gt in ALL_GT if dist.get(gt, Fraction(0)) == 0]
        if not zeros:
            continue
        tgt2_gt = random.choice(zeros)
        tgt2_pr = Fraction(0)

        # 4) 해(솔루션) 찾기: 미리 계산된 pairs에서 필터링만으로 구함
        sols = []
        for x in pairs:
            if x["ph_count"] != ph_count:
                continue
            d2 = x["dist"]
            if d2.get(tgt1_gt, Fraction(0)) != tgt1_pr:
                continue
            if d2.get(tgt2_gt, Fraction(0)) != tgt2_pr:
                continue
            sols.append((x["P1"], x["P2"]))
            if len(sols) > 6:  # 너무 많으면 컷
                break

        if len(sols) == 0:
            continue
        if len(sols) > 6:
            continue

        # ----------- 문제 생성 -------------
        problem_code = f"M3-{random.randint(1,999):03d}"
        pid = ID_PREFIX + sha10(f"{time.time()}_{problem_code}_{random.random()}")

        # 링크 설명
        if pattern == "L2I1":
            lg = list(linked)
            link_desc = f"({lg[0]}/{lg[0].lower()}), ({lg[1]}/{lg[1].lower()})는 연관이며 교차 없음(완전연관). 나머지 1쌍은 독립이다."
        else:
            link_desc = "(A/a), (B/b), (D/d)는 모두 연관이며 교차 없음(완전연관)."

        ph_desc = (
            "※ 표현형은 **대문자 개수(k)**가 아니라, 각 유전자의 **우성 표현 여부(A+/B+/D+)**로 구분한다.\n"
            "- A형질: A-이면 발현, aa이면 비발현\n"
            "- B형질: B-이면 발현, bb이면 비발현\n"
            "- D형질: D-이면 발현, dd이면 비발현\n"
            "따라서 표현형은 (A+/A-, B+/B-, D+/D-) 형태로 나타난다.\n"
        )

        problem_text_md = (
            f"문제 제목 : Matrix3 일반유전 추론 ({problem_code})\n\n"
            f"(A/a), (B/b), (D/d) 세 유전자는 각각 다른 형질을 결정한다(일반유전).\n"
            f"{link_desc}\n\n"
            f"- 부모 P1, P2는 미지수이다.\n"
            f"- 자손의 **표현형 종류는 {ph_count}가지**이다.\n"
            f"- 자손 유전자형 **{tgt1_gt}** 의 확률 = **{frac_to_str(tgt1_pr)}**\n"
            f"- 자손 유전자형 **{tgt2_gt}** 의 확률 = **0**\n\n"
            f"{ph_desc}"
            f"조건을 만족하는 모든 (P1,P2) 조합을 구하시오."
        )

        ask_line_md = "가능한 모든 P1, P2 조합을 구하고, 자손 표현형의 종류와 각 확률을 구하시오."

        # 정답
        answer_lines = []
        answer_lines.append(f"총 정답 후보: {len(sols)}개\n")
        for idx_s, (c1, c2) in enumerate(sols, 1):
            answer_lines.append(f"[후보 {idx_s}]")
            answer_lines.append(f"- P1 = {pstr(c1, pattern, linked)}")
            answer_lines.append(f"- P2 = {pstr(c2, pattern, linked)}")

            sol_dist = offspring(pattern, linked, c1, c2)
            sol_ph = ph_dist(sol_dist)
            for k in sorted(sol_ph.keys()):
                if sol_ph[k] > 0:
                    answer_lines.append(f"  - {k} : {frac_to_str(sol_ph[k])}")
            answer_lines.append("")

        answer_text_md = "\n".join(answer_lines)

        solution_md = (
            "### 해설(자동)\n"
            "- 주어진 표현형 수와 두 유전자형 확률 조건을 만족하는 모든 (P1,P2)를 전수검사로 탐색했다.\n"
            "- 일반유전이므로 표현형은 대문자 개수가 아니라 A/B/D 각각의 우성 발현 여부 조합이다.\n"
        )

        payload = {
            "module": MODULE,
            "id_prefix": ID_PREFIX,
            "problem_code": problem_code,
            "pattern": pattern,
            "linked_genes": list(linked),
            "constraints": {
                "phenotype_count": ph_count,
                "target1": {"genotype": tgt1_gt, "prob": frac_to_str(tgt1_pr)},
                "target2": {"genotype": tgt2_gt, "prob": "0"},
            },
            "solutions": [
                {"P1": pstr(c1, pattern, linked), "P2": pstr(c2, pattern, linked)}
                for (c1, c2) in sols
            ],
            "problem_text_md": problem_text_md,
            "ask_line_md": ask_line_md,
            "answer_text_md": answer_text_md,
            "solution_md": solution_md,
        }

        return Problem(pid, payload)

    raise RuntimeError("문제 생성 실패: 조건 완화 필요")

# ----------------------------
# PACK 저장
# ----------------------------

def make_pack(n=30):
    items=[]
    for i in range(1,n+1):
        pr = build_one()
        items.append({
            "id":pr.pid,
            "pid":pr.pid,
            "module":MODULE,
            "id_prefix":ID_PREFIX,
            "difficulty":2,
            "problem_text_md":pr.payload["problem_text_md"],
            "ask_line_md":pr.payload["ask_line_md"],
            "answer_text_md":pr.payload["answer_text_md"],
            "solution_md":pr.payload["solution_md"],
            "payload":pr.payload,
            "_qnum":i
        })

    pack={
        "module":MODULE,
        "id_prefix":ID_PREFIX,
        "created_at":time.strftime("%Y-%m-%d %H:%M:%S"),
        "items":items
    }

    out_path=os.path.join(OUT_DIR,f"pack_{MODULE}_{int(time.time())}.json")
    with open(out_path,"w",encoding="utf-8") as f:
        json.dump(pack,f,ensure_ascii=False,indent=2)

    return out_path

if __name__=="__main__":
    print("[OK] PACK saved:", make_pack(30))
