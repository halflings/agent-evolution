import sys
from pathlib import Path

# Add skill scripts folder to path
SKILL_SCRIPTS_PATH = Path(__file__).parent / ".agents" / "skills" / "agent-evolution" / "scripts"
if str(SKILL_SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS_PATH))

import test_extract_history_lib

# Expose test functions
test_clean_user_content_caveat = test_extract_history_lib.test_clean_user_content_caveat
test_clean_user_content_str = test_extract_history_lib.test_clean_user_content_str
test_clean_user_content_list = test_extract_history_lib.test_clean_user_content_list
test_parse_session_file = test_extract_history_lib.test_parse_session_file
test_parse_antigravity_session = test_extract_history_lib.test_parse_antigravity_session
