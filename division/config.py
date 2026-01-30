# division_pack/config.py

LOCUS_IDS = ["E", "F", "G"]                  # loci
ALLELES  = ["E", "e", "F", "f", "G", "g"]     # table columns (upper/lower)
CELL_LABELS = ["가", "나", "다", "라", "마", "바"]

DEFAULT_N = 30
DEFAULT_MAX_TRIES_PER_PROBLEM = 2000

BLANK_RANGE = (9, 15)   # total number of '?' in the 6x6 allele table
MIN_KNOWN_PER_ROW = 4   # per cell row, at least 4 values remain known

# 여성 n(1)에서 X합=2 규칙 (네 기존 룰 유지)
FEMALE_X_N1_SUM2 = True
