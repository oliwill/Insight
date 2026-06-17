import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_analysis import (
    _build_dashboard_markdown,
    _count_index_rows,
    _dashboard_backup_path,
    restore_dashboard_backup,
)


def test_count_index_rows_ignores_headers_and_separator():
    index = """# Stock Wiki Index

| 代码 | 名称 | 最近分析 | 评分 | 资料数 |
|------|------|----------|------|--------|
| AAPL.US | Apple | 2026-06-03 | 88 | 3 |
| HIMS.US | Hims | 2026-06-03 | 74 | 2 |
"""

    assert _count_index_rows(index) == 2


def test_build_dashboard_markdown_includes_reason_and_counts():
    index = """| 代码 | 名称 | 最近分析 | 评分 | 资料数 |
|------|------|----------|------|--------|
| AAPL.US | Apple | 2026-06-03 | 88 | 3 |
"""
    recent_logs = [{"timestamp": "2026-06-03 10:00", "action": "dashboard_update", "detail": "manual refresh"}]

    dashboard = _build_dashboard_markdown(
        index_markdown=index,
        recent_logs=recent_logs,
        pending_tasks=4,
        update_reason="scheduled",
    )

    assert "> 更新来源: scheduled" in dashboard
    assert "- **跟踪股票**: 1" in dashboard
    assert "- **待处理任务**: 4" in dashboard
    assert "dashboard_update" in dashboard


def test_restore_dashboard_backup_copies_backup_content(tmp_path):
    dashboard = tmp_path / "Dashboard.md"
    backup = _dashboard_backup_path(dashboard)
    backup.write_text("backup content", encoding="utf-8")

    restored = restore_dashboard_backup(dashboard_path=dashboard, verbose=False)

    assert restored == backup
    assert dashboard.read_text(encoding="utf-8") == "backup content"
