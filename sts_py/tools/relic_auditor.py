from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sts_py.tools import wiki_audit


class RelicAuditor:
    """Thin compatibility wrapper around wiki_audit's relic-only pipeline."""

    def audit(
        self,
        *,
        repo_root: Path | str | None = None,
        enable_network: bool = True,
    ) -> dict[str, Any]:
        resolved_repo_root = Path(repo_root or Path.cwd()).resolve()
        raw_snapshot = wiki_audit.build_cli_raw_snapshot(
            resolved_repo_root,
            enable_network=enable_network,
            entity_types={"relic"},
        )
        return wiki_audit.run_audit_from_raw_snapshot(raw_snapshot, repo_root=resolved_repo_root)


def main() -> None:
    repo_root = Path.cwd().resolve()
    bundle = RelicAuditor().audit(repo_root=repo_root, enable_network=True)
    print(
        json.dumps(
            {
                "entity_types": ["relic"],
                "translation_findings": bundle["translation_audit"]["summary"],
                "completeness_findings": bundle["completeness_audit"]["summary"],
                "mechanics_findings": bundle["mechanics_audit"]["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
