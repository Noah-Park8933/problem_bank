# list_all_ids.py
import os, json, glob, csv

OUT_DIR = "output"
PACK_GLOB = os.path.join(OUT_DIR, "*_PACK_*.json")
CSV_OUT = os.path.join(OUT_DIR, "ALL_ID_LIST.csv")

def load_pack(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    pack_files = sorted(glob.glob(PACK_GLOB))
    if not pack_files:
        print(f"[INFO] PACK 파일이 없습니다: {PACK_GLOB}")
        return

    rows = []
    for p in pack_files:
        data = load_pack(p)
        module = data.get("module", "UNKNOWN")
        batch_id = data.get("batch_id", "UNKNOWN")
        for item in data.get("items", []):
            rows.append({
                "module": module,
                "batch_id": batch_id,
                "qnum": item.get("qnum", ""),
                "id": item.get("id", ""),
                "pack_file": os.path.basename(p),
            })

    # 콘솔 출력(보기 좋게)
    print("=" * 80)
    print(f"총 {len(rows)}개 ID (PACK 파일 {len(pack_files)}개)")
    print("=" * 80)
    for r in rows:
        print(f"{r['module']:6} | {r['batch_id']:10} | Q{int(r['qnum']):02d} | {r['id']}")

    # CSV 저장
    with open(CSV_OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["module", "batch_id", "qnum", "id", "pack_file"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print("=" * 80)
    print("✅ CSV 저장:", CSV_OUT)
    print("엑셀로 열면 전체 ID를 필터/정렬하면서 볼 수 있음.")
    print("=" * 80)

if __name__ == "__main__":
    main()
