# problem_pack.py
import time
import json
import os
import hashlib

def _to_jsonable(x):
    # PACK payload를 안전하게 json으로
    if isinstance(x, dict):
        return {str(k): _to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(v) for v in x]
    # Fraction 같은 거 문자열로 떨어뜨리기
    try:
        import fractions
        if isinstance(x, fractions.Fraction):
            return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)
    except Exception:
        pass
    # 기타: 그대로 두되, json 안 되면 str
    try:
        json.dumps(x, ensure_ascii=False)
        return x
    except Exception:
        return str(x)

class _PackProblemProxy:
    """
    pack.new_problem(...)이 반환하던 'pp' 객체 호환용.
    pp.set_texts(...), pp.set_answer(...), pp.set_solution(...), pp.set_meta(...)
    이런 식으로 쓰는 코드가 있으면 그대로 동작하게 함.
    """
    def __init__(self, pack, pid):
        self.pack = pack
        self.pid = pid
    @property
    def id(self) : 
        return self.pid
    def _item(self):
        return self.pack._id_to_item[self.pid]

    def set_texts(self, problem_text_md=None, ask_line_md=None):
        it = self._item()
        if problem_text_md is not None:
            it["problem_text_md"] = problem_text_md
        if ask_line_md is not None:
            it["ask_line_md"] = ask_line_md

    def set_answer(self, answer_text_md=None):
        it = self._item()
        if answer_text_md is not None:
            it["answer_text_md"] = answer_text_md

    def set_solution(self, solution_md=None):
        it = self._item()
        if solution_md is not None:
            it["solution_md"] = solution_md

    def set_difficulty(self, difficulty=None):
        it = self._item()
        if difficulty is not None:
            it["difficulty"] = int(difficulty)

    def set_payload(self, payload=None):
        it = self._item()
        if payload is not None:
            it["payload"] = _to_jsonable(payload)

    def set_meta(self, **kwargs):
        # payload 외에 따로 저장하고 싶으면 payload 안에 meta로 넣게 처리
        it = self._item()
        meta = it["payload"].get("_meta", {})
        meta.update(_to_jsonable(kwargs))
        it["payload"]["_meta"] = meta


class ProblemPack:
    def __init__(self, module_code: str, out_dir: str, id_prefix: str):
        self.module_code = module_code
        self.out_dir = out_dir
        self.id_prefix = id_prefix
        self.items = []
        self._id_to_item = {}

        if not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

    def _make_id(self):
        seed = f"{self.module_code}-{time.time_ns()}-{os.urandom(8)}"
        h = hashlib.sha1(seed.encode()).hexdigest()[:10]
        return f"{self.id_prefix}{h}"

    # ✅ 신버전 API
    def add(self, payload, problem_text_md, ask_line_md, answer_text_md, solution_md, difficulty=1):
        pid = self._make_id()
        it = {
            "id": pid,
            "module": self.module_code,
            "id_prefix": self.id_prefix,
            "difficulty": int(difficulty),
            "problem_text_md": problem_text_md,
            "ask_line_md": ask_line_md,
            "answer_text_md": answer_text_md,
            "solution_md": solution_md,
            "payload": _to_jsonable(payload),
        }
        self.items.append(it)
        self._id_to_item[pid] = it
        return pid

    # ✅ 구버전 호환 API: pack.new_problem(...)
    def new_problem(self, qnum=None, payload=None, difficulty=1, **kwargs):
        pid = self._make_id()
        it = {
            "id": pid,
            "module": self.module_code,
            "id_prefix": self.id_prefix,
            "difficulty": int(difficulty),
            "problem_text_md": kwargs.get("problem_text_md", ""),
            "ask_line_md": kwargs.get("ask_line_md", ""),
            "answer_text_md": kwargs.get("answer_text_md", ""),
            "solution_md": kwargs.get("solution_md", ""),
            "payload": _to_jsonable(payload if payload is not None else {}),
        }
        # qnum은 payload에 기록해두면 좋음
        if qnum is not None:
            it["payload"]["_qnum"] = int(qnum)

        self.items.append(it)
        self._id_to_item[pid] = it
        return _PackProblemProxy(self, pid)

    def save_json(self, filename=None):
        if filename is None:
            filename = f"{self.module_code}_{time.strftime('%Y%m%d_%H%M%S')}.pack.json"
        path = os.path.join(self.out_dir, filename)
        data = {
            "module": self.module_code,
            "id_prefix": self.id_prefix,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "items": self.items
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path
