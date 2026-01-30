# division_pack/model.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass(frozen=True)
class MeiosisEvent:
    """한 사람의 감수분열 사건을 고정하는 선택들(일관성 보장)."""
    dip_stage: str                   # "2n2" or "2n4"
    male_gamete: Optional[str]       # "X" or "Y" (남성일 때만, n2/n1 공통)
    female_hap_idx: Optional[int]    # 0/1 (여성일 때만, n2/n1 공통)
    autosome_choice: Dict[str, int]  # Aa 상염색체 locus에서 n단계에 남는 allele (0=upper,1=lower)

@dataclass(frozen=True)
class PersonTruth:
    sex: str                          # "M" or "F"
    x_haps: List[Dict[str, str]]      # hap(s): locus -> allele ("E" or "e")
    auto_geno: Dict[str, str]         # autosome locus -> "AA"/"Aa"/"aa" (A=upper, a=lower)
    event: MeiosisEvent

@dataclass(frozen=True)
class ProblemTruth:
    x_loci: List[str]                 # subset of ["E","F","G"] sized 1 or 2
    pos: Dict[str, str]               # locus -> "X" or "A1"/"A2"/...
    p1: PersonTruth
    p2: PersonTruth
