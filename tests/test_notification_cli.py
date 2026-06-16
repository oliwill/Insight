import subprocess
import sys
from pathlib import Path


def test_notify_telegram_fallback_handles_non_gbk_text_under_cp936():
    repo_root = Path(__file__).resolve().parents[1]
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(repo_root)!r}); "
        "from notification import notify_telegram; "
        "notify_telegram('Inbox monitor', '📬 Inbox scan complete')"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        env={"PYTHONIOENCODING": "cp936"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "UnicodeEncodeError" not in result.stderr
