import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "generator") not in sys.path:
    sys.path.insert(0, str(ROOT / "generator"))

try:
    from generator.run_proposal_generator import main
except ImportError:
    from run_proposal_generator import main

if __name__ == "__main__":
    main()
