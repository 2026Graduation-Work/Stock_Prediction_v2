from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[4] / ".github/workflows/news-supabase-sync.yml"


def test_news_sync_workflow_has_schedule_targets_secrets_and_runtime_guards() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'cron: "0 0 * * 1-5"' in text
    assert "workflow_dispatch:" in text
    for target in ("005930:삼성전자", "005380:현대차", "035720:카카오", "068270:셀트리온"):
        assert target in text
    for secret in ("NEWSAPI_AI_KEY", "SUPABASE_URL", "SUPABASE_SECRET_KEY"):
        assert f"${{{{ secrets.{secret} }}}}" in text
        assert f"{secret}=sk_" not in text
    assert "concurrency:" in text
    assert "cancel-in-progress: false" in text
    assert "https://download.pytorch.org/whl/cpu" in text
    assert "~/.cache/huggingface" in text
    assert "python-version: \"3.12\"" in text
    assert "permissions:\n  contents: read" in text
    assert "timeout-minutes:" in text
