#!/usr/bin/env python3
"""Create a human-readable summary of one discovery run."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generator/output"
STATUS = ROOT / "scheduler/status.json"
THESES = OUTPUT / "theses.json"
REPORT = ROOT / "analysis/run_summary.md"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def count_theses(data: dict) -> tuple[int, int, int, int]:
    theses = data.get("theses", [])
    if not isinstance(theses, list):
        theses = []
    counts = data.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    accepted = counts.get("validated", sum(str(t.get("decision", "")).upper() == "ACCEPT" for t in theses if isinstance(t, dict)))
    rejected = counts.get("rejected", sum(str(t.get("decision", "")).upper() == "REJECT" for t in theses if isinstance(t, dict)))
    quarantined = counts.get("quarantined", sum(str(t.get("decision", "")).upper() == "QUARANTINE" for t in theses if isinstance(t, dict)))
    return len(theses), int(accepted), int(rejected), int(quarantined)


def main() -> int:
    status = read_json(STATUS)
    theses = read_json(THESES)
    total, accepted, rejected, quarantined = count_theses(theses)
    metrics = status.get("stats", {}) if isinstance(status.get("stats"), dict) else {}
    generated_at = datetime.now(timezone.utc).isoformat()
    lines = [
        "# PyHok Discovery Run Summary",
        "",
        f"Generated: `{generated_at}`",
        "",
        "## Resultado em linguagem simples",
        "",
        f"- Foram analisadas **{total} teses** nesta execução.",
        f"- **{accepted}** foram aceitas para investigação; isso não significa que sejam verdadeiras.",
        f"- **{rejected}** foram rejeitadas, normalmente por repetição, falta de evidência ou excesso de conclusão.",
        f"- **{quarantined}** ficaram em quarentena para revisão.",
        "",
        "Uma tese é uma pergunta/hipótese de investigação. O sistema não está diagnosticando uma criança e não transforma um comportamento isolado em causa clínica.",
        "",
        "## Estado operacional",
        "",
        f"- Status: **{status.get('status', 'não informado')}**",
        f"- Último erro: `{status.get('last_error') or 'nenhum registrado'}`",
        f"- Ciclos totais registrados: **{metrics.get('total_runs', status.get('current_cycle_id') or 'não informado')}**",
        f"- Falhas acumuladas: **{metrics.get('failed_runs', 'não informado')}**",
        "",
        "## Como interpretar",
        "",
        "- Aceita = hipótese considerada legítima para continuar sendo investigada.",
        "- Rejeitada = não entrou no conhecimento ativo; a razão deve ser consultada nos logs da execução.",
        "- Evidência e validação são necessárias antes de qualquer conclusão.",
        "- Dados sintéticos não representam medições reais de crianças.",
        "",
        "## Links úteis",
        "",
        f"- Execução no GitHub Actions: https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'ls-matheus/pyhok-knowledge')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}",
        "- Logs detalhados: abra a execução acima e expanda o job.",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
