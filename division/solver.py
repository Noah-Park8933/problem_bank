# division_pack/solver.py
from __future__ import annotations

from itertools import combinations, permutations, product
from typing import Any, Dict, List, Optional, Tuple

from .config import LOCUS_IDS, ALLELES, CELL_LABELS
from .model import MeiosisEvent, PersonTruth, ProblemTruth
from .simulate import locus_positions, build_row_for_person_stage

# -------------------------
# Fast matching helpers
# -------------------------
def build_known_constraints(masked: Dict[str, Dict[str, Any]]) -> Dict[str, List[Tuple[str, int]]]:
    """label -> [(allele, value), ...] for known cells only"""
    known: Dict[str, List[Tuple[str, int]]] = {}
    for lab in CELL_LABELS:
        items: List[Tuple[str, int]] = []
        row = masked[lab]
        for a in ALLELES:
            v = row[a]
            if v != "?":
                items.append((a, int(v)))
        known[lab] = items
    return known

def row_matches_known(known_items: List[Tuple[str, int]], exp_row: Dict[str, int]) -> bool:
    for a, v in known_items:
        if exp_row[a] != v:
            return False
    return True

# -------------------------
# Candidate enumeration (exact)
# -------------------------
def iter_person_truth_candidates(
    sex: str,
    x_loci: List[str],
    pos: Dict[str, str],
) -> List[PersonTruth]:
    """
    solver용 완전탐색 후보(PersonTruth) 열거:
    - autosome genotype: 각 상염색체 locus AA/Aa/aa
    - Aa이면 n단계에서 남는 allele 방향 0/1
    - X hap: 남1개/여2개
    - 사건: dip_stage(2n2/2n4) + (남) gamete X/Y or (여) hap_idx 0/1
    """
    auto_loci = [lid for lid in LOCUS_IDS if pos[lid] != "X"]
    dip_stages = ["2n2", "2n4"]
    geno_opts = ["AA", "Aa", "aa"]
    candidates: List[PersonTruth] = []

    if sex == "M":
        hap_opts: List[List[Dict[str, str]]] = []
        for bits in product([0, 1], repeat=len(x_loci)):
            hap = {lid: (lid if b == 0 else lid.lower()) for lid, b in zip(x_loci, bits)}
            hap_opts.append([hap])

        for dip_stage in dip_stages:
            for mg in ["X", "Y"]:
                for x_haps in hap_opts:
                    for geno_tuple in product(geno_opts, repeat=len(auto_loci)):
                        auto_geno = {lid: g for lid, g in zip(auto_loci, geno_tuple)}
                        aa_loci = [lid for lid in auto_loci if auto_geno[lid] == "Aa"]
                        for choice_bits in product([0, 1], repeat=len(aa_loci)):
                            autosome_choice = {lid: b for lid, b in zip(aa_loci, choice_bits)}
                            event = MeiosisEvent(
                                dip_stage=dip_stage, male_gamete=mg, female_hap_idx=None, autosome_choice=autosome_choice
                            )
                            candidates.append(PersonTruth(sex=sex, x_haps=x_haps, auto_geno=auto_geno, event=event))
    else:
        hap_pair_opts: List[List[Dict[str, str]]] = []
        for bits1 in product([0, 1], repeat=len(x_loci)):
            hap1 = {lid: (lid if b == 0 else lid.lower()) for lid, b in zip(x_loci, bits1)}
            for bits2 in product([0, 1], repeat=len(x_loci)):
                hap2 = {lid: (lid if b == 0 else lid.lower()) for lid, b in zip(x_loci, bits2)}
                hap_pair_opts.append([hap1, hap2])

        for dip_stage in dip_stages:
            for hi in [0, 1]:
                for x_haps in hap_pair_opts:
                    for geno_tuple in product(geno_opts, repeat=len(auto_loci)):
                        auto_geno = {lid: g for lid, g in zip(auto_loci, geno_tuple)}
                        aa_loci = [lid for lid in auto_loci if auto_geno[lid] == "Aa"]
                        for choice_bits in product([0, 1], repeat=len(aa_loci)):
                            autosome_choice = {lid: b for lid, b in zip(aa_loci, choice_bits)}
                            event = MeiosisEvent(
                                dip_stage=dip_stage, male_gamete=None, female_hap_idx=hi, autosome_choice=autosome_choice
                            )
                            candidates.append(PersonTruth(sex=sex, x_haps=x_haps, auto_geno=auto_geno, event=event))

    return candidates

# -------------------------
# Cached expected rows per (sex, x_loci)
# -------------------------
# (sex, tuple(x_loci)) -> List[(exp_dip, exp_n2, exp_n1)]
_EXP_CACHE: Dict[Tuple[str, Tuple[str, ...]], List[Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]]] = {}

def get_exp_rows_cached(sex: str, x_loci: List[str]) -> List[Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]]:
    key = (sex, tuple(x_loci))
    if key in _EXP_CACHE:
        return _EXP_CACHE[key]

    pos = locus_positions(x_loci)
    cands = iter_person_truth_candidates(sex, x_loci, pos)

    out: List[Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]] = []
    for cand in cands:
        fake_truth = ProblemTruth(x_loci=x_loci, pos=pos, p1=cand, p2=cand)
        exp_dip = build_row_for_person_stage(fake_truth, cand, cand.event.dip_stage)
        exp_n2  = build_row_for_person_stage(fake_truth, cand, "n2")
        exp_n1  = build_row_for_person_stage(fake_truth, cand, "n1")
        out.append((exp_dip, exp_n2, exp_n1))

    _EXP_CACHE[key] = out
    return out

# -------------------------
# Feasibility check for one person group
# -------------------------
_STAGE_PERMS = list(permutations(["DIP", "N2", "N1"], 3))

def person_group_feasible(
    known: Dict[str, List[Tuple[str, int]]],
    labels_group: Tuple[str, str, str],
    sex: str,
    x_loci: List[str],
) -> bool:
    """
    (세포 3개 그룹, 성별, X좌 가정)에서
    어떤 PersonTruth + (label->stage 배정)이 존재하면 True.
    (최적화: known-only match + exp rows cache)
    """
    exp_rows_list = get_exp_rows_cached(sex, x_loci)

    k0 = known[labels_group[0]]
    k1 = known[labels_group[1]]
    k2 = known[labels_group[2]]

    for exp_dip, exp_n2, exp_n1 in exp_rows_list:
        for perm in _STAGE_PERMS:
            # 0
            if perm[0] == "DIP":
                if not row_matches_known(k0, exp_dip): 
                    continue
            elif perm[0] == "N2":
                if not row_matches_known(k0, exp_n2): 
                    continue
            else:
                if not row_matches_known(k0, exp_n1): 
                    continue

            # 1
            if perm[1] == "DIP":
                if not row_matches_known(k1, exp_dip): 
                    continue
            elif perm[1] == "N2":
                if not row_matches_known(k1, exp_n2): 
                    continue
            else:
                if not row_matches_known(k1, exp_n1): 
                    continue

            # 2
            if perm[2] == "DIP":
                if not row_matches_known(k2, exp_dip): 
                    continue
            elif perm[2] == "N2":
                if not row_matches_known(k2, exp_n2): 
                    continue
            else:
                if not row_matches_known(k2, exp_n1): 
                    continue

            return True

    return False

# -------------------------
# Main solver: enumerate answer solutions
# -------------------------
def count_answer_solutions(masked: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    masked table로부터 정답 해(사람분할 + 성별 + X좌)를 전부 열거.
    내부 유전자형이 여러 개여도 '정답 형태'가 같으면 1개로 묶음.
    """
    solutions: List[Dict[str, Any]] = []
    sol_keys = set()

    known = build_known_constraints(masked)

    # feasible memo per problem
    feasible_cache: Dict[Tuple[Tuple[str, str, str], str, Tuple[str, ...]], bool] = {}

    def feasible(group: Tuple[str, str, str], sex: str, x_loci: List[str]) -> bool:
        key = (group, sex, tuple(x_loci))
        if key in feasible_cache:
            return feasible_cache[key]
        ok = person_group_feasible(known, group, sex, x_loci)
        feasible_cache[key] = ok
        return ok

    # X좌 후보 6개: 3C1 + 3C2
    x_loci_candidates: List[List[str]] = [[lid] for lid in LOCUS_IDS]

    # 사람 분할 20개
    for p1_cells in combinations(CELL_LABELS, 3):
        p1_cells = tuple(sorted(p1_cells))
        p2_cells = tuple(sorted([c for c in CELL_LABELS if c not in p1_cells]))

        # 성별 2가지
        for sex_p1, sex_p2 in [("M", "F")]:
            for x_loci in x_loci_candidates:
                x_loci = sorted(x_loci)

                if not feasible(p1_cells, sex_p1, x_loci):
                    continue
                if not feasible(p2_cells, sex_p2, x_loci):
                    continue

                key = (p1_cells, sex_p1, tuple(x_loci))
                if key in sol_keys:
                    continue
                sol_keys.add(key)

                owner = {c: ("P1" if c in p1_cells else "P2") for c in CELL_LABELS}
                pos = locus_positions(x_loci)

                solutions.append({
                    "p1_cells": list(p1_cells),
                    "p2_cells": list(p2_cells),
                    "sex": {"P1": sex_p1, "P2": sex_p2},
                    "x_loci": x_loci,
                    "locus_positions": pos,
                    "owner": owner,
                })

    return solutions
