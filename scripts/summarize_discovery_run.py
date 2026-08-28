#!/usr/bin/env python3
"""Create human-readable, durable summaries for one discovery run."""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generator/output"
STATUS = ROOT / "scheduler/status.json"
THESES = OUTPUT / "theses.json"
REPORT = ROOT / "analysis/run_summary.md"
ARTIFACTS = ROOT / "analysis/artifacts"
INDEX = ARTIFACTS / "index.jsonl"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def theses_from(data: dict) -> list[dict]:
    value = data.get("theses", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def count_theses(data: dict) -> tuple[int, int, int, int]:
    theses = theses_from(data)
    counts = data.get("counts", {})
    counts = counts if isinstance(counts, dict) else {}
    accepted = counts.get("validated", sum(str(t.get("decision", "")).upper() == "ACCEPT" for t in theses))
    rejected = counts.get("rejected", sum(str(t.get("decision", "")).upper() == "REJECT" for t in theses))
    quarantined = counts.get("quarantined", sum(str(t.get("decision", "")).upper() == "QUARANTINE" for t in theses))
    return len(theses), int(accepted), int(rejected), int(quarantined)


def short_slug(text: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    words = re.findall(r"[a-z0-9]+", normalized)
    return "-".join(words[:6])[:48].strip("-") or fallback


def signal_files(signal_ids: list) -> list[str]:
    files = []
    signal_dir = ROOT / "data/signals"
    for signal_id in signal_ids:
        matches = sorted(signal_dir.glob(f"{signal_id}.json"))
        files.extend(str(path.relative_to(ROOT)) for path in matches)
    return files


def score(thesis: dict, name: str) -> str:
    review = thesis.get("review_result", {})
    if not isinstance(review, dict):
        return "não informado"
    value = review.get(name)
    return str(value) if value is not None else "não informado"


def thesis_artifact(thesis: dict, run_id: str, generated_at: str) -> tuple[str, dict]:
    thesis_id = str(thesis.get("thesis_id", "thesis-unknown"))
    title = str(thesis.get("hypothesis_template") or thesis.get("hypothesis") or thesis.get("description") or "tese sem título")
    decision = str(thesis.get("decision", "UNKNOWN")).upper()
    source_signals = thesis.get("required_signals", []) or thesis.get("available_signals", [])
    if not isinstance(source_signals, list):
        source_signals = []
    review = thesis.get("review_result", {})
    review = review if isinstance(review, dict) else {}
    artifact = {
        "artifact_type": "discovery_thesis_summary",
        "artifact_version": "1.0",
        "thesis_id": thesis_id,
        "run_id": run_id or None,
        "learned_at": thesis.get("timestamp") or generated_at,
        "decision": decision,
        "short_title": title[:120],
        "what_was_investigated": title,
        "source_signals": source_signals,
        "source_files": signal_files(source_signals),
        "source_opportunity": thesis.get("opportunity_id"),
        "domain": thesis.get("target_domain") or thesis.get("domain"),
        "epistemic_status": thesis.get("epistemic_status") or review.get("assigned_epistemic_status"),
        "epistemic_score": review.get("epistemic_score"),
        "novelty_score": review.get("novelty_score"),
        "coverage_gain": review.get("coverage_gain"),
        "evidence": review.get("verifier", {}).get("evidence_roots", []) if isinstance(review.get("verifier"), dict) else [],
        "evidence_strength": review.get("verifier", {}).get("evidence_strength_score") if isinstance(review.get("verifier"), dict) else None,
        "rejection_reason": thesis.get("rejection_reason") or review.get("quarantine_reason"),
        "learned": decision == "ACCEPT",
        "learning_outcome": ("registered_as_investigational_knowledge" if decision == "ACCEPT" else "not_learned"),
        "what_was_learned": ("A hipótese foi registrada como conhecimento investigável; ainda não foi comprovada." if decision == "ACCEPT" else "Nenhum novo conhecimento foi incorporado ao estado ativo."),
        "why_not_learned": (None if decision == "ACCEPT" else thesis.get("rejection_reason") or review.get("quarantine_reason") or "A revisão não autorizou a incorporação."),
        "learned_summary": ("Hipótese admitida e registrada para investigação futura; isso não significa que seja verdadeira." if decision == "ACCEPT" else "A execução não incorporou esta hipótese ao conhecimento ativo; a razão registrada deve orientar a próxima exploração."),
    }
    filename = f"{short_slug(title, 'thesis')}-{short_slug(thesis_id, 'id')}.md"
    body = [
        f"# {artifact['short_title']}", "",
        f"- **Decisão:** `{decision}`", f"- **Quando:** `{artifact['learned_at']}`", f"- **ID da tese:** `{thesis_id}`", "",
        "## Em linguagem simples", "", artifact["learned_summary"], "",
        "## O que foi investigado", "", title, "",
        "## De onde veio", "", f"- Sinais: {', '.join(f'`{s}`' for s in source_signals) or 'não informado'}", f"- Arquivos de origem: {', '.join(f'`{s}`' for s in artifact['source_files']) or 'não encontrados'}", f"- Oportunidade: `{artifact['source_opportunity'] or 'não informada'}`", f"- Domínio: `{artifact['domain'] or 'não informado'}`", "",
        "## Dados para estatísticas futuras", "", "```json", json.dumps(artifact, ensure_ascii=False, indent=2), "```", "",
        "> Este registro é uma hipótese de investigação. Não é diagnóstico nem evidência clínica sobre uma criança.", "",
    ]
    return filename, artifact | {"artifact_path": f"analysis/artifacts/{filename}"}


def write_thesis_artifacts(theses: list[dict], run_id: str, generated_at: str) -> list[dict]:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    records = []
    for thesis in theses:
        filename, record = thesis_artifact(thesis, run_id, generated_at)
        (ARTIFACTS / filename).write_text("\n".join([
            f"# {record['short_title']}", "",
            f"- **Decisão:** `{record['decision']}`", f"- **Quando:** `{record['learned_at']}`", f"- **ID da tese:** `{record['thesis_id']}`", "",
            "## Em linguagem simples", "", record["learned_summary"], "",
            "## O que foi investigado", "", record["what_was_investigated"], "",
            "## De onde veio", "", f"- Sinais: {', '.join(f'`{s}`' for s in record['source_signals']) or 'não informado'}", f"- Arquivos de origem: {', '.join(f'`{s}`' for s in record['source_files']) or 'não encontrados'}", f"- Oportunidade: `{record['source_opportunity'] or 'não informada'}`", f"- Domínio: `{record['domain'] or 'não informado'}`", "",
            "## Dados para estatísticas futuras", "", "```json", json.dumps(record, ensure_ascii=False, indent=2), "```", "",
            "> Este registro é uma hipótese de investigação. Não é diagnóstico nem evidência clínica sobre uma criança.", "",
        ]) + "\n", encoding="utf-8")
        records.append(record)
    with INDEX.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return records


def main() -> int:
    status = read_json(STATUS)
    theses_data = read_json(THESES)
    theses = theses_from(theses_data)
    total, accepted, rejected, quarantined = count_theses(theses_data)
    generated_at = datetime.now(timezone.utc).isoformat()
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    records = write_thesis_artifacts(theses, run_id, generated_at)
    metrics = status.get("stats", {}) if isinstance(status.get("stats"), dict) else {}
    lines = [
        "# PyHok Discovery Run Summary", "", f"Generated: `{generated_at}`", f"Run ID: `{run_id}`", "",
        "## Resultado em linguagem simples", "", f"- Foram analisadas **{total} teses** nesta execução.", f"- **{accepted}** foram aceitas para investigação; isso não significa que sejam verdadeiras.", f"- **{rejected}** foram rejeitadas, normalmente por repetição, falta de evidência ou excesso de conclusão.", f"- **{quarantined}** ficaram em quarentena para revisão.", "",
        f"- Aprendeu algo? **{'Sim, registrou uma hipótese investigável' if accepted else 'Não houve aprendizado incorporado'}**.", "- O que aprendeu: hipóteses aceitas foram registradas, mas continuam sem comprovação.", f"- Por que não aprendeu: {rejected + quarantined} teses não foram incorporadas por rejeição ou quarentena.", "",
        "Uma tese é uma pergunta/hipótese de investigação. O sistema não está diagnosticando uma criança e não transforma um comportamento isolado em causa clínica.", "",
        "## Estado operacional", "", f"- Status: **{status.get('status', 'não informado')}**", f"- Último erro: `{status.get('last_error') or 'nenhum registrado'}`", f"- Falhas acumuladas: **{metrics.get('failed_runs', 'não informado')}**", "",
        "## Artefatos desta execução", "", f"Foram gravados **{len(records)} artefatos** em `analysis/artifacts/`. Cada arquivo explica a tese e termina com dados estruturados para estatísticas futuras: quando foi registrada, de onde veio, o que investigava, decisão, evidências e pontuações.", "", "## Como interpretar", "", "- Aceita = hipótese legítima para continuar investigando, não verdade.", "- Rejeitada = não entrou no conhecimento ativo; a razão fica registrada.", "- Dados sintéticos não representam medições reais de crianças.", "",
        "## Links úteis", "", f"- Execução no GitHub Actions: https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'ls-matheus/pyhok-knowledge')}/actions/runs/{run_id}", "- Logs detalhados: abra a execução acima e expanda o job.",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
