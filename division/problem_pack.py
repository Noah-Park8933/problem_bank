# problem_pack.py
import json, os, random, string, datetime
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

def make_batch_id() -> str:
    d = datetime.datetime.now().strftime("%y%m%d")
    r = ''.join(random.choices(string.ascii_uppercase + string.digits, k=2))
    return f"{d}-{r}"  # 예: 260125-K9

def make_problem_id(module_code: str, batch_id: str, qnum: int) -> str:
    tail = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{module_code}-{batch_id}-Q{qnum:02d}-{tail}"

@dataclass
class PackedProblem:
    id: str
    module: str
    qnum: int
    seed: int
    payload: Dict[str, Any]  # 문제에 필요한 모든 데이터(표/정답/해설 등) 자유롭게 넣기

class ProblemPack:
    def __init__(self, module_code: str, out_dir: str = "output", batch_id: Optional[str] = None):
        self.module_code = module_code
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.batch_id = batch_id or make_batch_id()
        self.items: List[PackedProblem] = []

    def new_problem(self, qnum: int, payload: Dict[str, Any], seed: Optional[int] = None) -> PackedProblem:
        if seed is None:
            seed = random.randint(1, 2_000_000_000)
        pid = make_problem_id(self.module_code, self.batch_id, qnum)
        pp = PackedProblem(id=pid, module=self.module_code, qnum=qnum, seed=seed, payload=payload)
        self.items.append(pp)
        return pp

    def save_json(self, filename: Optional[str] = None) -> str:
        if filename is None:
            filename = f"{self.module_code}_PACK_{self.batch_id}.json"
        path = os.path.join(self.out_dir, filename)
        data = {
            "module": self.module_code,
            "batch_id": self.batch_id,
            "count": len(self.items),
            "items": [asdict(x) for x in self.items]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    @staticmethod
    def load_json(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

def pick_by_ids(pack_data: Dict[str, Any], ids: List[str]) -> List[Dict[str, Any]]:
    wanted = set(ids)
    return [item for item in pack_data["items"] if item["id"] in wanted]
