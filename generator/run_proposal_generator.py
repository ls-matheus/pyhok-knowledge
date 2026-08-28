from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parents[1]

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

MASTER_DOCUMENT_FILE = (
    ROOT / "docs/PYHOK_MASTER_ARCHITECTURE.md"
)

CONSTITUTION_FILE = (
    ROOT / "prompts/00_agent_constitution.system.txt"
)

CONTEXT_FILE = (
    ROOT / "generator/input/current_knowledge_context.json"
)

AUDIT_FILE = (
    ROOT / "generator/output/audit.json"
)

POLICY_FILE = (
    ROOT / "evolution/evolution-policy.json"
)

OUTPUT_FILE = (
    ROOT / "generator/output/proposal.json"
)


def read_text(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Arquivo não encontrado: {path}")

    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Arquivo não encontrado: {path}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"JSON inválido em {path}: {exc}"
        )


def build_context_if_needed() -> None:
    if CONTEXT_FILE.exists():
        return

    print("Building current repository context...")

    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT / "generator/build_agent_context.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout)

    if result.returncode != 0:
        if result.stderr:
            print(result.stderr)

        raise SystemExit(
            "Failed to build current repository context."
        )


def validate_audit(audit: dict[str, Any]) -> None:
    status = audit.get("status")

    if status == "NO_USEFUL_CHANGE":
        raise SystemExit(
            "Audit não encontrou oportunidade útil. "
            "Proposal Generator não será executado."
        )

    if status != "ANALYSIS_COMPLETE":
        raise SystemExit(
            f"Status de auditoria inválido: {status}"
        )

    opportunities = audit.get("opportunities")

    if not isinstance(opportunities, list):
        raise SystemExit(
            "Campo 'opportunities' inválido no audit.json."
        )

    if not opportunities:
        raise SystemExit(
            "Audit está completo, mas não contém oportunidades."
        )


def build_prompt(
    master_document: str,
    constitution: str,
    current_context: dict[str, Any],
    evolution_policy: dict[str, Any],
    audit: dict[str, Any],
) -> str:

    return f"""
Você é o PyHok Proposal Generator.

Sua responsabilidade é transformar uma oportunidade de evolução
identificada pelo Graph Auditor em uma proposta estruturada,
computável, justificável e compatível com o estado atual do
Knowledge Graph.

Você NÃO é o Auditor.
Você NÃO é o Validator.
Você NÃO é o Runtime.
Você NÃO é um sistema de diagnóstico.

Você NÃO deve modificar o repositório.

============================================================
IDIOMA OBRIGATÓRIO
============================================================

Todo conteúdo semântico gerado deve estar em português do Brasil (pt-BR).

Não traduza identificadores técnicos.

Preserve exatamente:

- IDs;
- signal_id;
- method_id;
- domain;
- nomes de campos;
- nomes técnicos;
- enum values;
- nomes de arquivos;
- componentes;
- schemas.

============================================================
QUATRO CAMADAS EPISTÊMICAS
============================================================

CAMADA 1 — MASTER DOCUMENT

Define o que é o PyHok, sua arquitetura, finalidade,
limites e princípios.

CAMADA 2 — AGENT CONSTITUTION

Define como o agente deve raciocinar e quais comportamentos
são proibidos.

CAMADA 3 — CURRENT KNOWLEDGE CONTEXT

Define o que realmente existe neste ciclo no repositório.

CAMADA 4 — EVOLUTION POLICY

Define o que pode ser proposto neste ciclo.

A ordem de autoridade é:

CURRENT KNOWLEDGE CONTEXT
+
EVOLUTION POLICY
+
AGENT CONSTITUTION
+
MASTER DOCUMENT

O Master Document NÃO cria capacidade operacional.

Se algo não existir no CURRENT KNOWLEDGE CONTEXT,
trate como UNKNOWN.

============================================================
REGRA FUNDAMENTAL
============================================================

O Auditor já respondeu:

"Existe uma oportunidade de evolução?"

Você deve responder:

"Qual proposta concreta representa essa oportunidade?"

O Validator responderá posteriormente:

"Essa proposta pode ser aceita?"

Não misture essas responsabilidades.

============================================================
REGRA DE COMPUTABILIDADE
============================================================

Uma proposta só pode utilizar infraestrutura explicitamente
existente no CURRENT KNOWLEDGE CONTEXT.

Nunca invente:

- sinais;
- métodos;
- sensores;
- APIs;
- capacidades de runtime;
- campos;
- schemas;
- identificadores;
- evidências;
- observações;
- dados pessoais;
- relações existentes.

Se uma oportunidade estiver marcada como:

COMPUTABLE_EVOLUTION

ela pode gerar uma proposta concreta.

Se estiver marcada como:

GAP

ela NÃO deve gerar uma QuestionEntity concreta que dependa
de infraestrutura inexistente.

============================================================
QUESTION ENTITY
============================================================

Quando a oportunidade for computável, a proposta deve representar
uma hipótese observacional computável.

Ela deve deixar claro:

1. o que está sendo observado;
2. qual sinal fornece a evidência;
3. qual método avalia a evidência;
4. qual domínio representa a hipótese;
5. qual fenômeno observacional está sendo distinguido;
6. por que a proposta é nova;
7. como preserva a variabilidade individual;
8. como preserva a incerteza;
9. por que a infraestrutura atual consegue avaliá-la.

Não faça diagnóstico.

Não afirme estados clínicos.

Não transforme uma hipótese em fato.

============================================================
INDIVIDUALIDADE
============================================================

Quando method_baseline_deviation estiver disponível e for pertinente,
priorize comparação com linha de base individual.

Não transforme diferença individual em diagnóstico.

============================================================
INCERTEZA
============================================================

Ausência de evidência NÃO significa evidência negativa.

Baixa qualidade NÃO significa ausência do fenômeno.

A proposta deve preservar explicitamente essa distinção.

============================================================
NOVIDADE
============================================================

A proposta precisa representar ganho real de conhecimento.

Não considere novidade suficiente:

- trocar palavras;
- trocar IDs;
- mudar somente limiar;
- mudar somente janela temporal;
- duplicar hipótese existente.

Compare:

- perguntas existentes;
- sinais;
- métodos;
- domínio;
- fenômeno;
- dimensão temporal;
- relações.

============================================================
OPERAÇÕES AUTORIZADAS
============================================================

Consulte a Evolution Policy.

Não invente operações.

Uma proposta pode representar apenas uma operação autorizada.

============================================================
SAÍDA
============================================================

Produza exatamente uma proposta para a oportunidade de maior prioridade
entre as oportunidades fornecidas.

Não produza múltiplas propostas.

Para proposal_id, utilize o padrão "prop_" + opportunity_id.
Para question_id e id da pergunta, utilize o padrão descritivo combinando domínio, sinal e método (por exemplo: "q_motor_instability_pointer_velocity_deviation").

Se nenhuma oportunidade puder ser transformada em proposta concreta,
retorne:

{{
  "status": "NO_PROPOSAL",
  "proposal": null
}}

Caso exista uma oportunidade computável, retorne:

{{
  "status": "PROPOSAL_READY",
  "proposal": {{
    "proposal_id": "...",
    "operation": "...",
    "opportunity_id": "...",
    "domain": "...",
    "question": {{
      "question_id": "...",
      "description": "...",
      "signal_ids": [],
      "method_ids": []
      "method_ids": [],
      "id": "...",
      "hypothesis": "...",
      "required_signals": [],
      "evaluation_trigger": {{
        "logical_operator": "AND",
        "rules": [
          {{
            "signal_id": "...",
            "operator": ">",
            "threshold": 0.0,
            "window_ms": 1000
          }}
        ]
      }},
      "evaluation_model": {{
        "method_id": "...",
        "version": "1.0.0",
        "parameters": {{}}
      }},
      "evidence_model": {{
        "base_strength": 0.8,
        "decay_rate_per_sec": 0.1
      }},
      "cortex_weights": {{
        "focus": 0.0,
        "stress": 0.0,
        "autonomy": 0.0,
        "fatigue": 0.0
      }}
    }},
    "rationale": "...",
    "novelty_justification": "...",
    "computability_justification": "...",
    "individuality_justification": "...",
    "uncertainty_justification": "...",
    "evidence_basis": {{
      "signals": [],
      "methods": []
    }},
    "confidence": 0.0
  }}
}}

Não escreva explicações fora do JSON.

============================================================
MASTER DOCUMENT
============================================================

{master_document}

============================================================
AGENT CONSTITUTION
============================================================

{constitution}

============================================================
CURRENT KNOWLEDGE CONTEXT
============================================================

{json.dumps(
    current_context,
    ensure_ascii=False,
    indent=2
)}

============================================================
EVOLUTION POLICY
============================================================

{json.dumps(
    evolution_policy,
    ensure_ascii=False,
    indent=2
)}

============================================================
AUDIT RESULT
============================================================

{json.dumps(
    audit,
    ensure_ascii=False,
    indent=2
)}

Agora gere somente a proposta JSON.
"""


def main() -> None:
    if not API_KEY:
        raise SystemExit(
            "GEMINI_API_KEY is missing."
        )

    build_context_if_needed()

    master_document = read_text(
        MASTER_DOCUMENT_FILE
    )

    constitution = read_text(
        CONSTITUTION_FILE
    )

    current_context = read_json(
        CONTEXT_FILE
    )

    evolution_policy = read_json(
        POLICY_FILE
    )

    audit = read_json(
        AUDIT_FILE
    )

    validate_audit(audit)

    response_schema = {
        "type": "object",
        "required": [
            "status",
            "proposal",
        ],
        "properties": {
            "status": {
                "type": "string",
                "enum": [
                    "PROPOSAL_READY",
                    "NO_PROPOSAL",
                ],
            },
            "proposal": {
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "string",
                    },
                    "operation": {
                        "type": "string",
                    },
                    "opportunity_id": {
                        "type": "string",
                    },
                    "domain": {
                        "type": "string",
                    },
                    "question": {
                        "type": "object",
                        "properties": {
                            "question_id": {
                                "type": "string",
                            },
                            "description": {
                                "type": "string",
                            },
                            "signal_ids": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                            "method_ids": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                            "id": {
                                "type": "string",
                            },
                            "hypothesis": {
                                "type": "string",
                            },
                            "required_signals": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                            "evaluation_trigger": {
                                "type": "object",
                                "properties": {
                                    "logical_operator": {
                                        "type": "string",
                                        "enum": [
                                            "AND",
                                            "OR",
                                        ],
                                    },
                                    "rules": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "signal_id": {
                                                    "type": "string",
                                                },
                                                "operator": {
                                                    "type": "string",
                                                },
                                                "threshold": {
                                                    "type": "number",
                                                },
                                                "window_ms": {
                                                    "type": "number",
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                            "evaluation_model": {
                                "type": "object",
                                "required": [
                                    "method_id",
                                    "version",
                                    "parameters",
                                ],
                                "properties": {
                                    "method_id": {
                                        "type": "string",
                                    },
                                    "version": {
                                        "type": "string",
                                    },
                                    "parameters": {
                                        "type": "object",
                                    },
                                },
                            },
                            "evidence_model": {
                                "type": "object",
                                "required": [
                                    "base_strength",
                                    "decay_rate_per_sec",
                                ],
                                "properties": {
                                    "base_strength": {
                                        "type": "number",
                                    },
                                    "decay_rate_per_sec": {
                                        "type": "number",
                                    },
                                },
                            },
                            "cortex_weights": {
                                "type": "object",
                                "required": [
                                    "focus",
                                    "stress",
                                    "autonomy",
                                    "fatigue",
                                ],
                                "properties": {
                                    "focus": {
                                        "type": "number",
                                    },
                                    "stress": {
                                        "type": "number",
                                    },
                                    "autonomy": {
                                        "type": "number",
                                    },
                                    "fatigue": {
                                        "type": "number",
                                    },
                                },
                            },
                        },
                    },
                    "rationale": {
                        "type": "string",
                    },
                    "novelty_justification": {
                        "type": "string",
                    },
                    "computability_justification": {
                        "type": "string",
                    },
                    "individuality_justification": {
                        "type": "string",
                    },
                    "uncertainty_justification": {
                        "type": "string",
                    },
                    "evidence_basis": {
                        "type": "object",
                        "properties": {
                            "signals": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                            "methods": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                        },
                    },
                    "confidence": {
                        "type": "number",
                    },
                },
            },
        },
    }

    prompt = build_prompt(
        master_document=master_document,
        constitution=constitution,
        current_context=current_context,
        evolution_policy=evolution_policy,
        audit=audit,
    )

    client = genai.Client(
        api_key=API_KEY
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )

    try:
        result = json.loads(
            response.text
        )
    except json.JSONDecodeError as exc:
        print(response.text)
        raise SystemExit(
            f"Gemini returned invalid JSON: {exc}"
        )

    if result.get("status") == "PROPOSAL_READY":
        proposal = result.get("proposal")

        if not proposal:
            raise SystemExit(
                "PROPOSAL_READY sem proposal."
            )

        required = [
            "proposal_id",
            "operation",
            "opportunity_id",
            "domain",
            "question",
            "rationale",
            "novelty_justification",
            "computability_justification",
            "individuality_justification",
            "uncertainty_justification",
            "evidence_basis",
            "confidence",
        ]

        missing = [
            field
            for field in required
            if field not in proposal
        ]

        if missing:
            raise SystemExit(
                "Proposal incompleta. Campos ausentes: "
                + ", ".join(missing)
            )

        question = proposal.get("question")

        if not isinstance(question, dict):
            raise SystemExit(
                "Proposal inválida: question deve ser um objeto."
            )

        question_required = [
            "question_id",
            "description",
            "signal_ids",
            "method_ids",
            "id",
            "hypothesis",
            "required_signals",
            "evaluation_trigger",
            "evaluation_model",
            "evidence_model",
            "cortex_weights",
        ]

        question_missing = [
            field
            for field in question_required
            if field not in question
        ]

        if question_missing:
            raise SystemExit(
                "Question incompleta. Campos ausentes: "
                + ", ".join(question_missing)
            )

        evaluation_model = question.get(
            "evaluation_model"
        )

        if not isinstance(evaluation_model, dict):
            raise SystemExit(
                "evaluation_model deve ser um objeto."
            )

        evaluation_required = [
            "method_id",
            "version",
            "parameters",
        ]

        evaluation_missing = [
            field
            for field in evaluation_required
            if field not in evaluation_model
        ]

        if evaluation_missing:
            raise SystemExit(
                "evaluation_model incompleto. Campos ausentes: "
                + ", ".join(evaluation_missing)
            )


    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print("=== PROPOSAL RESULT ===")
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    print(
        f"\nProposal written to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
