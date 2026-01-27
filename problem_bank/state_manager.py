from dataclasses import dataclass, field
from typing import Dict, Set

@dataclass
class AppState:
    selected_uids: Set[str] = field(default_factory=set)
    # uid -> difficulty label
    difficulty: Dict[str, str] = field(default_factory=dict)
    # uid -> "selected" 표시(체크박스와 동일하지만 표시용)
    marked: Set[str] = field(default_factory=set)

def ensure_state(st):
    if "app_state" not in st.session_state:
        st.session_state.app_state = AppState()
    return st.session_state.app_state