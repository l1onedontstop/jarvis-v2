"""pytest 公共配置 — 把项目 src/ 加入 sys.path。"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
SPEECH = SRC / "speech"

for p in (str(SRC), str(SPEECH)):
    if p not in sys.path:
        sys.path.insert(0, p)
