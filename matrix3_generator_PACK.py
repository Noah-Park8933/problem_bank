# matrix3_generator_PACK.py
# Matrix3 (일반유전) – 2연관+1독립(L2I1) 전용 / 복수 정답(≤3) 허용 / 빠른 생성 버전
# (A/a), (B/b), (D/d) / 완전연관(교차 없음)
# 표현형: A/B/D 각각의 우성 발현 여부 조합 (A+/A-, B+/B-, D+/D-)

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

ALL_GT = []
for A2 in ["AA","Aa","aa"]:
    for B2 in ["BB","Bb","bb"]:
        for D2 in ["DD","Dd","dd"]:
            ALL_GT.append(A2 + B2 + D2)

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

def gam_phase(h1,h2):
    if h1==h2: return {h1:Fraction(1)}
    return {h1:Fraction(1,2), h2:Fraction(1,2)}

def gam_single(g):
    a1,a2=g[0],g[1]
    if a1==a2: return {a1:Fraction(1)}
    return {a1:Fraction(1,2), a2:Fraction(1,2)}

# ----------------------------
# 자손 분포 계산 (L2I1 전용)
# ----------------------------

def offspring_L2I1(linked, P1, P2):
    def gams(P):
        gA,gB,gD=P["gA"],P["gB"],P["gD"]

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
# 부모 후보 생성 (L2I1 전용)
# ----------------------------

def enum_parents_L2I1(linked):
    out=[]
    for gA in G1:
        for gB in G1:
            for gD in G1:
                if set(linked)=={"A","B"}:
                    phs=phases2(gA,gB)
                    for ph in phs:
                        out.append({"gA":gA,"gB":gB,"gD":gD,"phase2":ph})
                elif set(linked)=={"A","D"}:
                    phs=phases2(gA,gD)
                    for ph in phs:
                        out.append({"gA":gA,"gB":gB,"gD":gD,"phase2":ph})
                elif set(linked)=={"B","D"}:
                    phs=phases2(gB,gD)
                    for ph in phs:
                        out.append({"gA":gA,"gB":gB,"gD":gD,"phase2":ph})
                else:
                    raise RuntimeError("invalid linked")
    return out

def pstr_L2I1(P,linked):
    g=P["gA"]+P["gB"]+P["gD"]
    return f"{g} (연관상:{P['phase2'][0]}/{P['phase2'][1]})"

# ----------------------------
# 빠른 솔루션 카운트 (≤3 초과면 즉시 중단)
# ----------------------------

def ph_count_of_dist(d):
    pd = ph_dist(d)
    return sum(1 for v in pd.values() if v > 0)

def count_solutions_upto3(cands, linked, ph_count, conds):
    sols=[]
    for c1 in cands:
        for c2 in cands:
            d2 = offspring_L2I1(linked, c1, c2)
            if ph_count_of_dist(d2) != ph_count:
                continue
            ok=True
            for gt, pr in conds:
                if d2.get(gt, Fraction(0)) != pr:
                    ok=False
                    break
            if ok:
                sols.append((c1,c2))
                if len(sols) > 3:   # ✅ 3개 초과면 컷
                    return sols
    return sols

# ----------------------------
# 문제 생성 (≤3개 답 허용 / 필요시 조건 3개로 자동 강화)
# ----------------------------

@dataclass
class Problem:
    pid:str
    payload:Dict[str,Any]

def build_one(max_tries=30000):
    lopts=[("A","B"),("A","D"),("B","D")]

    # 네가 원하면 이 allowed 리스트를 없애도 됨(성공률 더 올라감)
    allowed = [
        Fraction(1,16), Fraction(3,16),
        Fraction(1,8), Fraction(3,8),
        Fraction(1,4), Fraction(3,4),
        Fraction(1,2), Fraction(9, 16)
    ]

    # linked별 후보 캐시
    cand_cache = {}

    for _ in range(max_tries):
        linked = random.choice(lopts)
        if linked not in cand_cache:
            cand_cache[linked] = enum_parents_L2I1(linked)
        cands = cand_cache[linked]

        # 1) (P1,P2) 먼저 뽑기
        P1 = random.choice(cands)
        P2 = random.choice(cands)

        dist = offspring_L2I1(linked, P1, P2)
        ph_count = ph_count_of_dist(dist)
        if not (3 <= ph_count <= 6):
            continue

        # 2) 되는 조건 1개: allowed 확률 중 dist에 있는 것
        possibles = [(gt,pr) for gt,pr in dist.items() if pr in allowed]
        if not possibles:
            possibles = [(gt,pr) for gt,pr in dist.items() if pr > 0]
        tgt1_gt, tgt1_pr = random.choice(possibles)

        # 3) 안되는 조건 1개: 0 확률 유전자형
        zeros = [gt for gt in ALL_GT if dist.get(gt, Fraction(0)) == 0]
        if not zeros:
            continue
        tgt2_gt = random.choice(zeros)
        tgt2_pr = Fraction(0)

        conds = [(tgt1_gt, tgt1_pr), (tgt2_gt, tgt2_pr)]

        # 4) 검증: 해 개수(≤3)인지 확인
        sols = count_solutions_upto3(cands, linked, ph_count, conds)

        # 해 0이면 버림(거의 없음)
        if len(sols) == 0:
            continue

        # 해가 1~3이면 채택
        if 1 <= len(sols) <= 3:
            final_conds = conds
            final_sols = sols

        else:
            # ✅ 4번째 조건 추가(자동 강화)
            possibles3 = [(gt,pr) for gt,pr in dist.items()
                          if (gt,pr) not in [(tgt1_gt,tgt1_pr),(tgt3_gt,tgt3_pr)] and pr > 0]
            if not possibles3:
                continue
            tgt4_gt, tgt4_pr = random.choice(possibles3)
            conds4 = conds3 + [(tgt4_gt, tgt4_pr)]

            sols4 = count_solutions_upto3(cands, linked, ph_count, conds4)
            if len(sols4) == 0 or len(sols4) > 3:
                continue

            final_conds = conds4
            final_sols = sols4
        # ----------- 문제 텍스트 생성 -------------
        problem_code=f"M3-{random.randint(1,999):03d}"
        pid = ID_PREFIX + sha10(f"{time.time()}_{problem_code}_{random.random()}")

        lg=list(linked)
        link_desc=f"({lg[0]}/{lg[0].lower()}), ({lg[1]}/{lg[1].lower()})는 연관이며 교차 없음(완전연관). 나머지 1쌍은 독립이다."

        ph_desc=(
            "※ 표현형은 **대문자 개수(k)**가 아니라, 각 유전자의 **우성 표현 여부(A+/B+/D+)**로 구분한다.\n"
            "- A형질: A-이면 발현, aa이면 비발현\n"
            "- B형질: B-이면 발현, bb이면 비발현\n"
            "- D형질: D-이면 발현, dd이면 비발현\n"
            "따라서 표현형은 (A+/A-, B+/B-, D+/D-) 형태로 나타난다.\n"
        )

        cond_lines=[]
        for (gt,pr) in final_conds:
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
            f"{ph_desc}"
            f"조건을 만족하는 모든 (P1,P2) 조합을 구하시오."
        )

        ask_line_md = "가능한 모든 P1, P2 조합을 구하고, 자손 표현형의 종류와 각 확률을 구하시오."

        # 정답(최대 3개)
        answer_lines=[]
        answer_lines.append(f"총 정답 후보: {len(final_sols)}개\n")

        for idx_s,(c1,c2) in enumerate(final_sols,1):
            answer_lines.append(f"[후보 {idx_s}]")
            answer_lines.append(f"- P1 = {pstr_L2I1(c1,linked)}")
            answer_lines.append(f"- P2 = {pstr_L2I1(c2,linked)}")

            sol_dist = offspring_L2I1(linked,c1,c2)
            sol_ph = ph_dist(sol_dist)
            for k in sorted(sol_ph.keys()):
                if sol_ph[k] > 0:
                    answer_lines.append(f"  - {k} : {frac_to_str(sol_ph[k])}")
            answer_lines.append("")

        answer_text_md="\n".join(answer_lines)

        solution_md = (
            "### 해설(자동)\n"
            "- 먼저 (P1,P2)를 하나 잡고, 그 분포에서 ‘가능/불가능(0)’ 조건을 뽑아낸 뒤,\n"
            "  그 조건을 만족하는 (P1,P2) 후보 수가 1~3개가 되도록 검증했다.\n"
            "- 후보가 4개 이상이면 유전자형 확률 조건을 1개 추가하여 해를 줄였다.\n"
        )

        payload={
            "module":MODULE,
            "id_prefix":ID_PREFIX,
            "problem_code":problem_code,
            "pattern":"L2I1",
            "linked_genes":list(linked),
            "constraints":{
                "phenotype_count":ph_count,
                "conditions":[{"genotype":gt,"prob":("0" if pr==0 else frac_to_str(pr))} for gt,pr in final_conds]
            },
            "solutions":[
                {"P1":pstr_L2I1(c1,linked), "P2":pstr_L2I1(c2,linked)}
                for (c1,c2) in final_sols
            ],
            "problem_text_md":problem_text_md,
            "ask_line_md":ask_line_md,
            "answer_text_md":answer_text_md,
            "solution_md":solution_md,
        }

        return Problem(pid,payload)

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
