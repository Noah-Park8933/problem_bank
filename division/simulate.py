# division_pack/simulate.py
from __future__ import annotations

import random
from typing import Dict, List, Tuple

from .config import LOCUS_IDS, ALLELES, FEMALE_X_N1_SUM2
from .model import MeiosisEvent, PersonTruth, ProblemTruth

def choose_sexes(rng: random.Random) -> Tuple[str, str]:
    return ("M", "F") 

def choose_x_loci(rng: random.Random) -> List[str]:
    return [rng.choice(LOCUS_IDS)]

def locus_positions(x_loci: List[str]) -> Dict[str, str]:
    pos: Dict[str, str] = {lid: None for lid in LOCUS_IDS}
    for lid in x_loci:
        pos[lid] = "X"
    autos = [lid for lid in LOCUS_IDS if pos[lid] is None]
    labels = ["A1", "A2", "A3"]
    for i, lid in enumerate(autos):
        pos[lid] = labels[i]
    return pos

def rand_diploid_geno_Aa(rng: random.Random) -> str:
    return rng.choice(["AA", "Aa", "aa"])

def rand_allele_upper_lower(rng: random.Random, lid: str) -> str:
    return lid if rng.random() < 0.5 else lid.lower()

def sums_for(stage: str, sex: str, locus_is_x: bool, male_gamete: str | None) -> int:
    if stage == "2n2":
        if not locus_is_x:
            return 2
        return 1 if sex == "M" else 2

    if stage == "2n4":
        if not locus_is_x:
            return 4
        return 2 if sex == "M" else 4

    if stage == "n2":
        if not locus_is_x:
            return 2
        if sex == "M" and male_gamete == "Y":
            return 0
        return 2

    if stage == "n1":
        if not locus_is_x:
            return 1
        if sex == "M" and male_gamete == "Y":
            return 0
        if sex == "M":
            return 1
        return 2 if FEMALE_X_N1_SUM2 else 1

    raise ValueError(f"bad stage: {stage}")

def diploid_counts_from_Aa(geno: str, sum_val: int) -> Tuple[int, int]:
    if geno == "AA":
        return (sum_val, 0)
    if geno == "aa":
        return (0, sum_val)
    return (sum_val // 2, sum_val // 2)

def haploid_counts_from_allele(allele: str, sum_val: int, lid: str) -> Tuple[int, int]:
    if sum_val == 0:
        return (0, 0)
    return (sum_val, 0) if allele == lid else (0, sum_val)

def autosome_n_counts_from_Aa(geno: str, sum_val: int, choice: int) -> Tuple[int, int]:
    if geno == "AA":
        return (sum_val, 0)
    if geno == "aa":
        return (0, sum_val)
    return (sum_val, 0) if choice == 0 else (0, sum_val)

def make_person_truth(rng: random.Random, sex: str, x_loci: List[str], pos: Dict[str, str]) -> PersonTruth:
    auto_geno: Dict[str, str] = {}
    autosome_choice: Dict[str, int] = {}

    # autosomes
    for lid in LOCUS_IDS:
        if pos[lid] != "X":
            g = rand_diploid_geno_Aa(rng)
            auto_geno[lid] = g
            if g == "Aa":
                autosome_choice[lid] = rng.choice([0, 1])  # ✅ 사건 단위 고정

    # X haps (phase 유지)
    if sex == "M":
        hap = {lid: rand_allele_upper_lower(rng, lid) for lid in x_loci}
        x_haps = [hap]
       # male_gamete = rng.choice(["X", "Y"])  # ✅ n2/n1 공유
        male_gamete = "Y" if rng.random() < 0.75 else "X"
        female_hap_idx = None
    else:
        hap1 = {lid: rand_allele_upper_lower(rng, lid) for lid in x_loci}
        hap2 = {lid: rand_allele_upper_lower(rng, lid) for lid in x_loci}
        for _ in range(20):
            if hap1 != hap2:
                break
            hap2 = {lid: rand_allele_upper_lower(rng, lid) for lid in x_loci}
        x_haps = [hap1, hap2]
        male_gamete = None
        female_hap_idx = rng.choice([0, 1])  # ✅ n2/n1 공유

    dip_stage = rng.choice(["2n2", "2n4"])
    event = MeiosisEvent(
        dip_stage=dip_stage,
        male_gamete=male_gamete,
        female_hap_idx=female_hap_idx,
        autosome_choice=autosome_choice,
    )
    return PersonTruth(sex=sex, x_haps=x_haps, auto_geno=auto_geno, event=event)

def make_truth(rng: random.Random) -> ProblemTruth:
    while True:
        sex1, sex2 = choose_sexes(rng)
        x_loci = choose_x_loci(rng)          # X 1개
        pos = locus_positions(x_loci)

        p1 = make_person_truth(rng, sex1, x_loci, pos)
        p2 = make_person_truth(rng, sex2, x_loci, pos)

        # 너무 동일하면 정보 약해서 재추첨
        if (p1.sex, p1.auto_geno, p1.x_haps) == (p2.sex, p2.auto_geno, p2.x_haps):
            continue

        # ✅ 정보량 강제 1: dip_stage 다르게
        if p1.event.dip_stage == p2.event.dip_stage:
            continue

        # ✅ 정보량 강제 2: autosome 2개 중 최소 1개는 genotype 다르게
        autos = [lid for lid in LOCUS_IDS if pos[lid] != "X"]
        if all(p1.auto_geno[lid] == p2.auto_geno[lid] for lid in autos):
            continue

        return ProblemTruth(x_loci=x_loci, pos=pos, p1=p1, p2=p2)
def build_row_for_person_stage(truth: ProblemTruth, person: PersonTruth, stage: str) -> Dict[str, int]:
    row: Dict[str, int] = {}
    x_loci = truth.x_loci
    pos = truth.pos

    # X loci
    for lid in x_loci:
        sum_val = sums_for(stage, person.sex, True, person.event.male_gamete)

        if sum_val == 0:
            row[lid] = 0
            row[lid.lower()] = 0
            continue

        if stage in ("2n2", "2n4"):
            if person.sex == "M":
                allele = person.x_haps[0][lid]
                A_cnt, a_cnt = haploid_counts_from_allele(allele, sum_val, lid)
            else:
                a1 = person.x_haps[0][lid]
                a2 = person.x_haps[1][lid]
                if a1 == lid and a2 == lid:
                    geno = "AA"
                elif a1 == lid.lower() and a2 == lid.lower():
                    geno = "aa"
                else:
                    geno = "Aa"
                A_cnt, a_cnt = diploid_counts_from_Aa(geno, sum_val)
            row[lid], row[lid.lower()] = A_cnt, a_cnt
        else:
            # n2/n1: event-fixed
            if person.sex == "M":
                allele = person.x_haps[0][lid]  # X일 때만 sum_val>0
            else:
                allele = person.x_haps[person.event.female_hap_idx][lid]
            A_cnt, a_cnt = haploid_counts_from_allele(allele, sum_val, lid)
            row[lid], row[lid.lower()] = A_cnt, a_cnt

    # autosomes
    for lid in LOCUS_IDS:
        if pos[lid] == "X":
            continue
        sum_val = sums_for(stage, person.sex, False, person.event.male_gamete)
        geno = person.auto_geno[lid]
        if stage in ("2n2", "2n4"):
            A_cnt, a_cnt = diploid_counts_from_Aa(geno, sum_val)
        else:
            choice = person.event.autosome_choice.get(lid, 0)
            A_cnt, a_cnt = autosome_n_counts_from_Aa(geno, sum_val, choice)
        row[lid], row[lid.lower()] = A_cnt, a_cnt

    for a in ALLELES:
        if a not in row:
            raise RuntimeError("row build failed")
        if not isinstance(row[a], int):
            raise RuntimeError("row has non-int")
    return row

def build_person_three_rows(truth: ProblemTruth, person: PersonTruth) -> List[Dict[str, int]]:
    dip = person.event.dip_stage
    return [
        build_row_for_person_stage(truth, person, dip),
        build_row_for_person_stage(truth, person, "n2"),
        build_row_for_person_stage(truth, person, "n1"),
    ]

def shuffle_cell_labels(
    rng: random.Random,
    p1_rows: List[Dict[str, int]],
    p2_rows: List[Dict[str, int]],
) -> Tuple[Dict[str, Dict[str, int]], Dict[str, str]]:
    labels = ["가", "나", "다", "라", "마", "바"]
    rng.shuffle(labels)
    p1_labels = labels[:3]
    p2_labels = labels[3:]

    full: Dict[str, Dict[str, int]] = {}
    owner: Dict[str, str] = {}
    for lab, row in zip(p1_labels, p1_rows):
        full[lab] = row
        owner[lab] = "P1"
    for lab, row in zip(p2_labels, p2_rows):
        full[lab] = row
        owner[lab] = "P2"
    return full, owner
