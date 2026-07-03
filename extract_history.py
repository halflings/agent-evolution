import sys
from pathlib import Path

# Add skill scripts folder to path
SKILL_SCRIPTS_PATH = Path(__file__).parent / ".agents" / "skills" / "agent-evolution" / "scripts"
if str(SKILL_SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS_PATH))

from extract_history_lib import *

if __name__ == "__main__":
    main()
