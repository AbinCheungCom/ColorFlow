"""Web 测试路径配置：把 web/ 目录加入 sys.path，使 `import app` / `import mcp_server` 可用"""

import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
