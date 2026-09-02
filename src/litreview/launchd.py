from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape


def launchd_plist(project_dir: Path, label: str = "com.local.paper-alert-bot") -> str:
    uv_path = _uv_path()
    stdout = project_dir / "logs" / "litreview.out.log"
    stderr = project_dir / "logs" / "litreview.err.log"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{escape(label)}</string>
  <key>WorkingDirectory</key>
  <string>{escape(str(project_dir))}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{escape(uv_path)}</string>
    <string>run</string>
    <string>litreview</string>
    <string>scheduled-run</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>{escape(str(stdout))}</string>
  <key>StandardErrorPath</key>
  <string>{escape(str(stderr))}</string>
</dict>
</plist>
"""


def _uv_path() -> str:
    return "/opt/homebrew/bin/uv"
