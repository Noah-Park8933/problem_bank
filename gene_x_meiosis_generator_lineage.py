# ============================================================
#  gene_x_auto_generator.py
#  (표 랜덤 변형 + 유일해석 + loader.py 100% 호환 + 난이도 + ㄱㄴㄷ 다양화)
# ============================================================
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import random, json, hashlib, base64
from dataclasses import asdict, is_dataclass

def to_jsonable(x):
    if is_dataclass(x):
        return asdict(x)
    if isinstance(x, dict):
        return {k: to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_jsonable(v) for v in x]
    return x


# ============================================================
# Utils
# ============================================================
def jdump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)

def stable_hash(obj: Any) -> str:
    obj = to_jsonable(obj)
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]

SYMBOL_KR = {"eung": "㉠", "nieun": "㉡", "digeut": "㉢", "rieul": "㉣"}

SUM_KEYS = ("sum_en","sum_er","sum_nd","sum_dr")

CHOICES = ["①","②","③","④","⑤"]

# ============================================================
# ㄱ‧ㄴ‧ㄷ 문항 Pool (다양화)
# ㄱ 종류 = 합/비교/조건식 등
# ㄴ 종류 = ㉠, ㉡, ㉢, ㉣ 중 무작위 + 알렐 비교
# ㄷ 종류 = Y염색체 여부, 성염색체 분기 등
# ============================================================

# ㄱ 유형
G_PATTERNS = [
    "a + b = {val}",
    "b + c = {val}",
    "a + c = {val}",
    "a ⟂ b 여부는 {tf}",     # 이건 단순 참/거짓 문구 변형용
]

# ㄴ 유형
N_SYMBOL_CHOICES = ["eung","nieun","digeut","rieul"]

# ㄷ 유형
D_PATTERNS = [
    "III에 Y 염색체가 있다.",
    "III에 X 염색체만 존재한다.",
    "III는 X-linked 유전자를 가진다.",
    "III는 성염색체가 단일이다.",
]

# ============================================================
# World (lineage-correct)
# ============================================================
def alleles_of_geno(geno: str) -> Tuple[str,str]:
    return (geno[0], geno[1])

def add_counts(a: Dict[str,int], b: Dict[str,int]) -> Dict[str,int]:
    out = dict(a)
    for k,v in b.items():
        out[k] = out.get(k,0) + v
    return out

def counts_from_allele(allele: Optional[str], copies: int) -> Dict[str,int]:
    if allele is None:
        return {}
    return {allele: copies}

def AB_present(counts: Dict[str,int]) -> Tuple[int,int]:
    return (1 if counts.get("A",0)>0 else 0, 1 if counts.get("B",0)>0 else 0)

@dataclass(frozen=True)
class World:
    x_gene: str
    sex: str
    auto_geno: str
    x_geno: str
    left_auto: str
    right_auto: str
    left_x: Optional[str]
    right_x: Optional[str]


def derive_truth_by_stage(world: World) -> Dict[str,Dict[str,int]]:
    # I
    a0,a1 = alleles_of_geno(world.auto_geno)
    autoI={}
    if a0==a1: autoI[a0]=2
    else: autoI[a0]=1; autoI[a1]=1

    xI={}
    if world.sex=="M":
        xI[world.x_geno]=1
    else:
        x0,x1 = alleles_of_geno(world.x_geno)
        if x0==x1: xI[x0]=2
        else: xI[x0]=1; xI[x1]=1

    countsI = add_counts(autoI, xI)

    # II = right branch (copies=2)
    countsII = {}
    countsII = add_counts(countsII, counts_from_allele(world.right_auto,2))
    countsII = add_counts(countsII, counts_from_allele(world.right_x,2))

    # III = left branch (copies=1)
    countsIII = {}
    countsIII = add_counts(countsIII, counts_from_allele(world.left_auto,1))
    countsIII = add_counts(countsIII, counts_from_allele(world.left_x,1))

    return {"I":countsI,"II":countsII,"III":countsIII}

def y_present_in_stageIII(world: World)->bool:
    return (world.sex=="M" and world.left_x is None)

# ============================================================
# Symbol mappings
# ============================================================
def iter_symbol_mappings()->List[Dict[str,str]]:
    out=[]
    for pg in ("A","B"):
        if pg=="A":
            pair=("A","a"); other=("B","b")
        else:
            pair=("B","b"); other=("A","a")
        for e,r in (pair, pair[::-1]):
            for n,d in (other, other[::-1]):
                out.append({"eung":e,"rieul":r,"nieun":n,"digeut":d})
    return out

def iter_label_maps()->List[Dict[str,str]]:
    out=[]
    for ga in ("I","II","III"):
        for na in ("I","II","III"):
            if na==ga: continue
            for da in ("I","II","III"):
                if da in (ga,na): continue
                out.append({"ga":ga,"na":na,"da":da})
    return out

def compute_sums(counts: Dict[str,int], sm: Dict[str,str]) -> Dict[str,int]:
    def v(x): return counts.get(sm[x],0)
    return {
        "sum_en": v("eung")+v("nieun"),
        "sum_er": v("eung")+v("rieul"),
        "sum_nd": v("nieun")+v("digeut"),
        "sum_dr": v("digeut")+v("rieul"),
    }

# ============================================================
# Random world sampling
# ============================================================
def sample_world(rng: random.Random)->World:
    xg = rng.choice(["A","B"])
    ag = "B" if xg=="A" else "A"
    sex= rng.choice(["M","F"])
    auto_geno = rng.choice(["AA","Aa","aa"]) if ag=="A" else rng.choice(["BB","Bb","bb"])
    if xg=="A":
        x_geno = rng.choice(["A","a"]) if sex=="M" else rng.choice(["AA","Aa","aa"])
    else:
        x_geno = rng.choice(["B","b"]) if sex=="M" else rng.choice(["BB","Bb","bb"])

    a0,a1 = alleles_of_geno(auto_geno)
    if a0==a1: left_auto=right_auto=a0
    else:
        if rng.random()<0.5: left_auto,right_auto = a0,a1
        else: left_auto,right_auto = a1,a0

    if sex=="M":
        if rng.random()<0.5: left_x,right_x = x_geno,None
        else: left_x,right_x = None,x_geno
    else:
        x0,x1 = alleles_of_geno(x_geno)
        if x0==x1: left_x=right_x=x0
        else:
            if rng.random()<0.5: left_x,right_x = x0,x1
            else: left_x,right_x = x1,x0

    return World(x_gene=xg,sex=sex,auto_geno=auto_geno,x_geno=x_geno,
                 left_auto=left_auto,right_auto=right_auto,
                 left_x=left_x,right_x=right_x)

# ============================================================
# Build full true table
# ============================================================
def build_full_table(truth_by_stage, label_to_stage, sm):
    table={}
    for lab in ("ga","na","da"):
        st = label_to_stage[lab]
        counts = truth_by_stage[st]
        Ap,Bp = AB_present(counts)
        sums = compute_sums(counts, sm)
        table[lab] = {
            "A_present": Ap,
            "B_present": Bp,
            **sums
        }
    return table

# ============================================================
# 표 변형: from FULL → OBSERVED(mask)
# ============================================================
def make_observed(
    full: Dict[str,Any],
    rng: random.Random,
    difficulty: int
)->Optional[Dict[str,Any]]:

    # 난이도별 공개 정책
    if difficulty==1:  # very easy
        reveal_P = 1.0
        reveal_S = 0.9
        min_reveal = 8
    elif difficulty==2: # easy
        reveal_P = 0.9
        reveal_S = 0.7
        min_reveal = 7
    elif difficulty==3: # normal
        reveal_P = 0.75
        reveal_S = 0.55
        min_reveal = 5
    elif difficulty==4: # hard
        reveal_P = 0.6
        reveal_S = 0.4
        min_reveal = 4
    else: # killer
        reveal_P = 0.5
        reveal_S = 0.25
        min_reveal = 3

    # 모든 합
    pos=[]
    for lab in ("ga","na","da"):
        for k in SUM_KEYS:
            pos.append((lab,k,full[lab][k]))

    posv={0:[],2:[],4:[]}
    for p in pos:
        if p[2] in posv:
            posv[p[2]].append(p)

    if not posv[0] or not posv[2] or not posv[4]:
        return None

    # a,b,c 3개의 위치 선정
    p0 = rng.choice(posv[0])
    p2 = rng.choice(posv[2])
    p4 = rng.choice(posv[4])
    triple=[("a",p0),("b",p2),("c",p4)]
    rng.shuffle(triple)

    obs={"cells":{},"pairing_constraint":("eung","rieul")}

    # presence 마스킹
    for lab in ("ga","na","da"):
        Ap=full[lab]["A_present"]
        Bp=full[lab]["B_present"]
        Aobs = Ap if rng.random()<reveal_P else None
        Bobs = Bp if rng.random()<reveal_P else None
        obs["cells"][lab] = {"A_present":Aobs,"B_present":Bobs}
        for k in SUM_KEYS: obs["cells"][lab][k] = None

    # a,b,c 배치
    for letter,(lab,k,val) in triple:
        obs["cells"][lab][k] = letter

    # 나머지 일부 숫자 공개
    reveal_cnt=3
    for (lab,k,val) in pos:
        if obs["cells"][lab][k] in ("a","b","c"): continue
        if rng.random()<reveal_S:
            obs["cells"][lab][k] = val
            reveal_cnt += 1

    # 최소 공개 만족
    if reveal_cnt < min_reveal:
        hidden=[(lab,k,val) for (lab,k,val) in pos if obs["cells"][lab][k] is None]
        rng.shuffle(hidden)
        need = min_reveal - reveal_cnt
        for i in range(min(need,len(hidden))):
            lab,k,val = hidden[i]
            obs["cells"][lab][k] = val

    return obs

# ============================================================
# Solver (유일해석 필수)
# ============================================================
def solve(observed, truth_by_stage):
    sols=[]
    for lm in iter_label_maps():
        for sm in iter_symbol_mappings():
            implied={}
            ok=True
            for lab in ("ga","na","da"):
                st=lm[lab]
                counts=truth_by_stage[st]
                Ap,Bp = AB_present(counts)
                sums = compute_sums(counts, sm)
                cobs = observed["cells"][lab]

                if cobs["A_present"] is not None and cobs["A_present"] != Ap:
                    ok=False; break
                if cobs["B_present"] is not None and cobs["B_present"] != Bp:
                    ok=False; break

                for k in SUM_KEYS:
                    vobs = cobs[k]
                    if vobs is None: continue
                    vtrue = sums[k]
                    if isinstance(vobs,int):
                        if vtrue!=vobs: ok=False; break
                    else:
                        # a/b/c
                        if vobs not in ("a","b","c"):
                            ok=False; break
                        if vobs in implied and implied[vobs]!=vtrue:
                            ok=False; break
                        implied[vobs]=vtrue
                if not ok: break
            if not ok: continue
            if set(implied.keys()) != {"a","b","c"}: continue
            if sorted(implied.values()) != [0,2,4]: continue
            sols.append({"label_to_stage":lm,"sym_map":sm,"abc_map":implied})
    return sols

# ============================================================
# ㄱ‧ㄴ‧ㄷ 생성 (패턴 다양화)
# ============================================================
def build_gnd(sol, world, rng: random.Random, target_choice:str):

    want_g,want_n,want_d = {
        "①":(True, False,False),
        "②":(False,True, False),
        "③":(False,False,True),
        "④":(True, True, False),
        "⑤":(False,True, True),
    }[target_choice]

    abc = sol["abc_map"]

    # ㄱ 만들기
    gpat = rng.choice(G_PATTERNS)
    # 가능한 값
    a_plus_b = abc["a"]+abc["b"]  # 2/4/6
    options=[2,4,6]
    if want_g: k=a_plus_b
    else:
        others=[x for x in options if x!=a_plus_b]
        k=rng.choice(others)
    g_stmt = gpat.format(val=k, tf=("참" if want_g else "거짓"))
    g_truth = (a_plus_b==k)

    # ㄴ 만들기
    sym_choice = rng.choice(N_SYMBOL_CHOICES)
    symbol_kor = SYMBOL_KR[sym_choice]
    true_allele = sol["sym_map"][sym_choice]
    alleles=["A","a","B","b"]
    if want_n:
        allele_word = true_allele
    else:
        allele_word = rng.choice([x for x in alleles if x!= true_allele])
    n_stmt = f"{symbol_kor}은 {allele_word}이다."
    n_truth = (allele_word == true_allele)

    # ㄷ 만들기
    dpat = rng.choice(D_PATTERNS)
    y_true = y_present_in_stageIII(world)
    if want_d == y_true:
        d_stmt = dpat
        d_truth = True
    else:
        # negate
        if "않" not in dpat:
            d_stmt = dpat.replace("있다","없다").replace("존재한다","존재하지 않는다")
        else:
            d_stmt = dpat
        d_truth = False

    if (g_truth,n_truth,d_truth) != (want_g,want_n,want_d):
        raise RuntimeError("GND mismatch")

    return {
        "g":g_truth, "n":n_truth, "d":d_truth,
        "g_stmt":g_stmt, "n_stmt":n_stmt, "d_stmt":d_stmt,
        "answer_choice": target_choice
    }

# ============================================================
# Render (loader.py 호환)
# ============================================================
def build_table_grid(observed):
    def pm(x):
        if x is None: return "?"
        return "○" if x==1 else "×"
    def vd(x):
        return "?" if x is None else str(x)
    grid=[["세포","대립유전자A","대립유전자B","㉠+㉡","㉠+㉣","㉡+㉢","㉢+㉣"]]
    for lab,name in [("ga","(가)"),("na","(나)"),("da","(다)")]:
        c=observed["cells"][lab]
        grid.append([
            name,
            pm(c["A_present"]),
            pm(c["B_present"]),
            vd(c["sum_en"]),
            vd(c["sum_er"]),
            vd(c["sum_nd"]),
            vd(c["sum_dr"]),
        ])
    return grid

def render_item(obj, module, id_prefix, diagram_file, difficulty):
    observed = obj["observed"]
    grid = build_table_grid(observed)

    # MD table
    md_lines=["| 세포 | A | B | ㉠+㉡ | ㉠+㉣ | ㉡+㉢ | ㉢+㉣ |",
              "|-----|---|---|-----:|-----:|-----:|-----:|"]
    for r in grid[1:]:
        md_lines.append(
            f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |"
        )
    table_md="\n".join(md_lines)

    보기_md = (
        "<보기>\n"
        f"ㄱ. {obj['judged']['g_stmt']}\n"
        f"ㄴ. {obj['judged']['n_stmt']}\n"
        f"ㄷ. {obj['judged']['d_stmt']}\n"
    )

    problem_md = (
        "사람의 유전 형질 (가)는 대립유전자 A/a, (나)는 대립유전자 B/b에 의해 결정된다.\n"
        "(가)와 (나)의 유전자 중 하나는 X 염색체에 있다.\n"
        "표는 사람 P의 세포 (가)~(다)에서 A와 B의 유무 및 ㉠~㉣ 중 2개의 DNA 상대량을 더한 값이다.\n"
        "그림은 P의 G1기 세포로부터 정자가 형성되는 과정을 나타낸 것이다. (가)~(다)는 I~III를 순서 없이 나타내며, II는 중기 세포이다.\n"
        f"{SYMBOL_KR['eung']}~{SYMBOL_KR['rieul']}는 A,a,B,b를 순서 없이 나타내고, {SYMBOL_KR['eung']}은 {SYMBOL_KR['rieul']}과 대립유전자이다.\n"
        "a~c는 0,2,4를 순서 없이 나타낸다. 돌연변이와 교차는 고려하지 않는다.\n\n"
        + table_md
        + "\n\n"
        + f"![diagram]({diagram_file})\n\n"
        + 보기_md
        + "\n① ㄱ  ② ㄴ  ③ ㄷ  ④ ㄱ, ㄴ  ⑤ ㄴ, ㄷ"
    )

    payload={
        "_given_table": grid,                # loader 표 호환
        "diagram_file": diagram_file,        # loader 이미지 호환
        "observed": observed,
        "solution": to_jsonable(obj["solution"]),
        "world": to_jsonable(obj["world"]),
        "difficulty": difficulty,
        "gnd": {
            "g":obj["judged"]["g_stmt"],
            "n":obj["judged"]["n_stmt"],
            "d":obj["judged"]["d_stmt"],
        }
    }

    pid=f"{id_prefix}{stable_hash(payload)}"
    return {
        "id":pid,
        "module":module,
        "id_prefix":id_prefix,
        "difficulty":difficulty,
        "problem_text_md":problem_md,
        "ask_line_md":"이에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?",
        "answer_text_md":obj["judged"]["answer_choice"],
        "solution_md":f"정답: {obj['judged']['answer_choice']}",
        "payload":payload
    }

# ============================================================
# Generate ONE
# ============================================================
def generate_one(rng, target_choice, difficulty):
    for _ in range(300):  # 충분한 재시도
        w = sample_world(rng)
        truth = derive_truth_by_stage(w)

        lm = rng.choice(iter_label_maps())
        sm = rng.choice(iter_symbol_mappings())
        full = build_full_table(truth, lm, sm)

        obs = make_observed(full, rng, difficulty)
        if obs is None: continue

        sols = solve(obs, truth)
        if len(sols)!=1: continue
        sol = sols[0]

        judged = build_gnd(sol, w, rng, target_choice)
        return {
            "world":w, "observed":obs,
            "solution":sol, "judged":judged
        }
    return None

# ============================================================
# generate_pack
# ============================================================
def generate_pack(
    n:int,
    seed:int,
    module:str="260916_GDDI",
    id_prefix:str="260916_GDDI_",
    diagram_file:str="diagram_2609.png",
    difficulty:int=3
):
    rng=random.Random(seed)
    items=[]
    sigset=set()
    stats={"try":0,"ok":0,"dup":0,"fail":0,"by_answer":{c:0 for c in CHOICES}}

    target_cycle=[]
    while len(target_cycle)<n:
        target_cycle.extend(CHOICES)
    target_cycle=target_cycle[:n]

    for target in target_cycle:
        for _ in range(5000):
            stats["try"]+=1
            obj=generate_one(rng,target,difficulty)
            if obj is None:
                stats["fail"]+=1
                continue

            sig = jdump({
                "observed":obj["observed"],
                "g":obj["judged"]["g_stmt"],
                "n":obj["judged"]["n_stmt"],
                "d":obj["judged"]["d_stmt"],
                "ans":obj["judged"]["answer_choice"]
            })
            if sig in sigset:
                stats["dup"]+=1
                continue
            sigset.add(sig)

            item = render_item(
                obj,
                module=module,
                id_prefix=id_prefix,
                diagram_file=diagram_file,
                difficulty=difficulty
            )
            items.append(item)
            stats["ok"]+=1
            stats["by_answer"][target]+=1
            break

    return {
        "module":module,
        "id_prefix":id_prefix,
        "count":len(items),
        "stats":stats,
        "items":items
    }


# ============================================================
# MAIN
# ============================================================
if __name__=="__main__":
    pack=generate_pack(n=30,seed=20260202,difficulty=3)
    with open("260916_GDDI_pack.json","w",encoding="utf-8") as f:
        json.dump(pack,f,ensure_ascii=False,indent=2)
    print("Saved pack:", pack["count"], "stats:", pack["stats"])
