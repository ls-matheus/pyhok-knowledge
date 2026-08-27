from __future__ import annotations

import copy
import hashlib
import math
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evolution.graph.knowledge_graph import KnowledgeGraph
from evolution.epistemic.quarantine import read_rejected_claims, REJECTED_CLAIMS_FILE


def _safe_score(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or isinstance(val, bool):
            return default
        f = float(val)
        if not math.isfinite(f):
            return default
        return max(0.0, min(1.0, round(f, 4)))
    except (ValueError, TypeError):
        return default


def _tokenize(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()
    cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
    words = re.findall(r'[a-z0-9_]{3,}', cleaned)
    stop_words = {'the', 'and', 'that', 'this', 'with', 'from', 'for', 'when', 'then', 'have', 'has', 'into'}
    return {w for w in words if w not in stop_words}


class EpistemicDiscoveryEngine:
    def __init__(
        self,
        quarantine_file: Path = REJECTED_CLAIMS_FILE,
        diversity_weight: float = 0.20,
        random_seed: int | None = None,
    ):
        self.quarantine_file = quarantine_file
        self.diversity_weight = max(0.0, min(1.0, diversity_weight))
        self.rng = random.Random(random_seed)
        self._historical_proposals: list[dict[str, Any]] = []

    def register_historical_proposal(self, proposal: dict[str, Any]) -> None:
        if isinstance(proposal, dict):
            self._historical_proposals.append(copy.deepcopy(proposal))

    def detect_opportunities(
        self,
        knowledge_state: dict[str, Any] | None,
        graph: KnowledgeGraph | None = None,
    ) -> list[dict[str, Any]]:
        state = knowledge_state or {}
        if graph is None:
            graph = KnowledgeGraph()
            graph.build_from_dataset(state)

        opportunities: list[dict[str, Any]] = []

        # 1. Strategy A: Gaps
        gap_signals = graph.find_signals_without_theses() if hasattr(graph, "find_signals_without_theses") else graph.find_unconnected_signals()
        if not gap_signals:
            gap_signals = graph.find_unconnected_signals()
        signals_map = {s.get('id'): s for s in state.get('signals', []) if isinstance(s, dict) and s.get('id')}
        for sig_id in gap_signals:
            sig_data = signals_map.get(sig_id, {})
            domain = sig_data.get('domain', 'general')
            opp_id = f'opp_gap_{sig_id}_{hashlib.sha256(sig_id.encode()).hexdigest()[:6]}'
            opportunities.append({
                'opportunity_id': opp_id,
                'opportunity_type': 'GAP',
                'target_domain': domain,
                'source_entities': [sig_id],
                'description': f'Observational gap: Signal {sig_id} in domain {domain} has zero investigational theses.',
                'evidence_gap_score': 1.0,
                'novelty_score': 0.90,
                'coverage_gain': 0.85,
                'contradiction_value': 0.0,
                'binding_potential': 0.95,
            })

        # 2. Strategy B: Incomplete Theses
        incomplete = graph.find_incomplete_theses()
        for item in incomplete:
            th_id = item['thesis_id']
            unbound = item['unbound_variables']
            opp_id = f'opp_incomplete_{th_id}_{len(unbound)}'
            opportunities.append({
                'opportunity_id': opp_id,
                'opportunity_type': 'INCOMPLETE_THESIS',
                'target_domain': 'open_investigation',
                'source_entities': [th_id] + [v.get('id', '') for v in unbound if isinstance(v, dict)],
                'description': f'Incomplete investigation: Thesis {th_id} contains {len(unbound)} UNBOUND variable(s).',
                'evidence_gap_score': 0.70,
                'novelty_score': 0.60,
                'coverage_gain': 0.50,
                'contradiction_value': 0.0,
                'binding_potential': 1.0,
            })

        # 3. Strategy C: Contradiction Discovery
        questions = state.get('questions', [])
        for i, q1 in enumerate(questions):
            if not isinstance(q1, dict):
                continue
            for q2 in questions[i + 1:]:
                if not isinstance(q2, dict):
                    continue
                contra = self._find_contradiction(q1, q2)
                if contra:
                    opp_id = f'opp_contra_{contra["contradiction_id"]}'
                    opportunities.append({
                        'opportunity_id': opp_id,
                        'opportunity_type': 'CONTRADICTION',
                        'target_domain': 'conflict_resolution',
                        'source_entities': [q1.get('id'), q2.get('id')],
                        'description': f'Contradiction detected between {q1.get("id")} and {q2.get("id")}: {contra["conflict_type"]}',
                        'evidence_gap_score': 0.90,
                        'novelty_score': 0.95,
                        'coverage_gain': 0.60,
                        'contradiction_value': 1.0,
                        'binding_potential': 0.80,
                        'contradiction_id': contra['contradiction_id'],
                    })

        # 4. Strategy D: Unexplored Cross-Domain Relations
        all_signals = list(signals_map.keys())
        if len(all_signals) >= 2:
            for i in range(min(5, len(all_signals))):
                for j in range(i + 1, min(i + 4, len(all_signals))):
                    s1 = all_signals[i]
                    s2 = all_signals[j]
                    d1 = signals_map.get(s1, {}).get('domain', 'd1')
                    d2 = signals_map.get(s2, {}).get('domain', 'd2')
                    opp_id = f'opp_relation_{s1}_{s2}'
                    opportunities.append({
                        'opportunity_id': opp_id,
                        'opportunity_type': 'UNEXPLORED_RELATION',
                        'target_domain': f'{d1}_{d2}',
                        'source_entities': [s1, s2],
                        'description': f'Unexplored cross-relational coupling between {s1} ({d1}) and {s2} ({d2}).',
                        'evidence_gap_score': 0.80,
                        'novelty_score': 0.85 if d1 != d2 else 0.65,
                        'coverage_gain': 0.75,
                        'contradiction_value': 0.0,
                        'binding_potential': 0.70,
                    })

        # 5. Strategy E: Multi-Thematic Combinations
        all_theses = state.get("open_theses", [])
        if len(all_theses) >= 2:
            for i in range(min(3, len(all_theses))):
                for j in range(i + 1, min(i + 3, len(all_theses))):
                    t1 = all_theses[i]
                    t2 = all_theses[j]
                    t1_id = t1.get("thesis_id", f"th_{i}")
                    t2_id = t2.get("thesis_id", f"th_{j}")
                    opp_id = f"opp_combo_{t1_id[:8]}_{t2_id[:8]}"
                    opportunities.append({
                        "opportunity_id": opp_id,
                        "opportunity_type": "COMBINATION",
                        "target_domain": "synthetic_combination",
                        "source_entities": [t1_id, t2_id],
                        "description": f"Multi-thematic combination synthesising hypotheses {t1_id} and {t2_id}.",
                        "evidence_gap_score": 0.85,
                        "novelty_score": 0.92,
                        "coverage_gain": 0.80,
                        "contradiction_value": 0.0,
                        "binding_potential": 0.85,
                    })

        # 6. Strategy F: Topological Bridges
        island_pairs = graph.find_potential_bridges() if hasattr(graph, "find_potential_bridges") else []
        for src_node, tgt_node in island_pairs:
            opp_id = f"opp_bridge_{src_node[:8]}_{tgt_node[:8]}"
            opportunities.append({
                "opportunity_id": opp_id,
                "opportunity_type": "BRIDGE",
                "target_domain": "graph_bridging",
                "source_entities": [src_node, tgt_node],
                "description": f"Topological bridge connecting isolated graph components {src_node} and {tgt_node}.",
                "evidence_gap_score": 0.88,
                "novelty_score": 0.90,
                "coverage_gain": 0.88,
                "contradiction_value": 0.0,
                "binding_potential": 0.80,
            })

        # 7. Score, Deduplicate, Penalize Negative Memory & Rank
        scored_opportunities = []
        prior_rejections = read_rejected_claims(self.quarantine_file)

        for opp in opportunities:
            scored = self._score_opportunity(opp, prior_rejections)
            if scored['exploration_priority'] > 0.10:
                scored_opportunities.append(scored)

        scored_opportunities.sort(key=lambda x: x['exploration_priority'], reverse=True)
        return scored_opportunities

    def _find_contradiction(self, q1: dict[str, Any], q2: dict[str, Any]) -> dict[str, Any] | None:
        s1 = set(q1.get('required_signals', []))
        s2 = set(q2.get('required_signals', []))
        if s1 and s1 == s2:
            r1 = q1.get('evaluation_trigger', {}).get('rules', [])
            r2 = q2.get('evaluation_trigger', {}).get('rules', [])
            if len(r1) == len(r2) == 1 and isinstance(r1[0], dict) and isinstance(r2[0], dict):
                rule1 = r1[0]
                rule2 = r2[0]
                if rule1.get('signal_id') == rule2.get('signal_id'):
                    op1 = rule1.get('operator')
                    op2 = rule2.get('operator')
                    if (op1 == '>' and op2 == '<') or (op1 == '<' and op2 == '>'):
                        contra_id = f'contra_{q1.get("id")}_{q2.get("id")}'
                        return {
                            'contradiction_id': contra_id,
                            'claim_a_id': q1.get('id'),
                            'claim_b_id': q2.get('id'),
                            'shared_signals': list(s1),
                            'conflict_type': 'OPERATOR_INVERSION',
                            'status': 'DETECTED',
                            'detected_at': datetime.now(timezone.utc).isoformat(),
                        }
        return None

    def _score_opportunity(
        self,
        opp: dict[str, Any],
        prior_rejections: list[dict[str, Any]]
    ) -> dict[str, Any]:
        scored = copy.deepcopy(opp)
        desc = scored.get('description', '')
        tokens = _tokenize(desc)

        novelty = _safe_score(scored.get('novelty_score', 0.5))
        gap = _safe_score(scored.get('evidence_gap_score', 0.5))
        coverage = _safe_score(scored.get('coverage_gain', 0.5))
        contra = _safe_score(scored.get('contradiction_value', 0.0))
        binding = _safe_score(scored.get('binding_potential', 0.5))

        repetition_penalty = 0.0
        for past in self._historical_proposals:
            past_tokens = _tokenize(str(past.get('description', '') or past.get('hypothesis', '')))
            if past_tokens:
                jaccard = len(tokens & past_tokens) / len(tokens | past_tokens)
                if jaccard > 0.60:
                    repetition_penalty = max(repetition_penalty, jaccard * 0.50)

        for rej in prior_rejections:
            rej_tokens = _tokenize(str(rej.get('hypothesis', '')))
            if rej_tokens:
                jaccard = len(tokens & rej_tokens) / len(tokens | rej_tokens)
                if jaccard > 0.60:
                    repetition_penalty = max(repetition_penalty, 0.75)

        info_gain = _safe_score((gap * 0.40) + (coverage * 0.30) + (binding * 0.30))

        raw_priority = (
            (novelty * 0.30) +
            (info_gain * 0.30) +
            (contra * 0.25) +
            (coverage * 0.15) -
            repetition_penalty
        )
        jitter = self.rng.uniform(-0.02, 0.02)
        final_priority = _safe_score(raw_priority + jitter)

        scored['novelty_score'] = novelty
        scored['information_gain_score'] = info_gain
        scored['exploration_priority'] = final_priority
        scored['created_at'] = datetime.now(timezone.utc).isoformat()
        return scored

    def generate_open_thesis(
        self,
        opportunity: dict[str, Any],
        cycle_id: str | None = None
    ) -> dict[str, Any]:
        opp_id = opportunity.get('opportunity_id', 'opp_unknown')
        opp_type = opportunity.get('opportunity_type', 'GAP')
        sources = opportunity.get('source_entities', [])
        domain = opportunity.get('target_domain', 'neuro_sensory')
        c_id = cycle_id or f'cycle_disc_{hashlib.sha256(opp_id.encode()).hexdigest()[:8]}'

        thesis_id = f'thesis_{opp_type.lower()}_{hashlib.sha256(f"{opp_id}_{c_id}".encode()).hexdigest()[:8]}'

        if opp_type == 'GAP':
            sig_target = sources[0] if sources else 'unknown_signal'
            template = f'Investigation of uncharacterized observational variance in signal {sig_target}.'
            open_vars = [
                {
                    'id': f'var_{sig_target}_predictor',
                    'variable_id': f'var_{sig_target}_predictor',
                    'name': f'Predictor for {sig_target}',
                    'role': 'predictor',
                    'type': 'signal',
                    'domain': domain,
                    'status': 'UNBOUND',
                    'candidate_values': [sig_target],
                    'value': None,
                    'binding': None,
                    'binding_source': None,
                },
                {
                    'id': 'var_functional_outcome',
                    'variable_id': 'var_functional_outcome',
                    'name': 'Observed Functional Outcome',
                    'role': 'outcome',
                    'type': 'metric',
                    'domain': domain,
                    'status': 'UNBOUND',
                    'candidate_values': [],
                    'value': None,
                    'binding': None,
                    'binding_source': None,
                }
            ]
            relational = [{
                'source_var': f'var_{sig_target}_predictor',
                'target_var': 'var_functional_outcome',
                'relation_type': 'HYPOTHESIZED_LINK',
                'description': f'Exploring if {sig_target} modulates functional outcome.'
            }]

        elif opp_type == 'CONTRADICTION':
            contra_id = opportunity.get('contradiction_id', 'contra_unknown')
            template = f'Resolving empirical contradiction {contra_id} under parameter boundary conditions.'
            open_vars = [
                {
                    'id': 'var_boundary_condition',
                    'variable_id': 'var_boundary_condition',
                    'name': 'Parameter Boundary Condition',
                    'role': 'condition',
                    'type': 'context',
                    'domain': domain,
                    'status': 'UNBOUND',
                    'candidate_values': [],
                    'value': None,
                    'binding': None,
                    'binding_source': None,
                }
            ]
        elif opp_type == 'COMBINATION':
            s1 = sources[0] if len(sources) > 0 else 'thesis_alpha'
            s2 = sources[1] if len(sources) > 1 else 'thesis_beta'
            template = f'Investigating synthesized interactions between hypotheses {s1} and {s2}.'
            open_vars = [
                {
                    'id': f'var_syn_{s1[:8]}',
                    'variable_id': f'var_syn_{s1[:8]}',
                    'name': f'Synthesis Core {s1}',
                    'role': 'predictor',
                    'type': 'hypothesis',
                    'domain': domain,
                    'status': 'UNBOUND',
                    'candidate_values': [s1],
                    'value': None,
                    'binding': None,
                    'binding_source': None,
                },
                {
                    'id': f'var_syn_{s2[:8]}',
                    'variable_id': f'var_syn_{s2[:8]}',
                    'name': f'Synthesis Outcome {s2}',
                    'role': 'outcome',
                    'type': 'hypothesis',
                    'domain': domain,
                    'status': 'UNBOUND',
                    'candidate_values': [s2],
                    'value': None,
                    'binding': None,
                    'binding_source': None,
                }
            ]
            relational = [{
                'source_var': f'var_syn_{s1[:8]}',
                'target_var': f'var_syn_{s2[:8]}',
                'relation_type': 'SYNTHESIZED_WITH',
                'description': f'Inter-hypothesis coupling between {s1} and {s2}'
            }]

        elif opp_type == 'BRIDGE':
            s1 = sources[0] if len(sources) > 0 else 'node_alpha'
            s2 = sources[1] if len(sources) > 1 else 'node_beta'
            template = f'Investigating topological bridge hypotheses between isolated components {s1} and {s2}.'
            open_vars = [
                {
                    'id': f'var_bridge_{s1[:8]}',
                    'variable_id': f'var_bridge_{s1[:8]}',
                    'name': f'Bridge Anchor {s1}',
                    'role': 'predictor',
                    'type': 'signal',
                    'domain': domain,
                    'status': 'UNBOUND',
                    'candidate_values': [s1],
                    'value': None,
                    'binding': None,
                    'binding_source': None,
                },
                {
                    'id': f'var_bridge_{s2[:8]}',
                    'variable_id': f'var_bridge_{s2[:8]}',
                    'name': f'Bridge Anchor {s2}',
                    'role': 'outcome',
                    'type': 'signal',
                    'domain': domain,
                    'status': 'UNBOUND',
                    'candidate_values': [s2],
                    'value': None,
                    'binding': None,
                    'binding_source': None,
                }
            ]
            relational = [{
                'source_var': f'var_bridge_{s1[:8]}',
                'target_var': f'var_bridge_{s2[:8]}',
                'relation_type': 'BRIDGES_GAP',
                'description': f'Topological bridge between {s1} and {s2}'
            }]

        else:
            s1 = sources[0] if len(sources) > 0 else 'sig_source'
            s2 = sources[1] if len(sources) > 1 else 'sig_target'
            template = f'Exploring relational coupling between {s1} and {s2} under cognitive load.'
            open_vars = [
                {
                    'id': f'var_{s1}',
                    'variable_id': f'var_{s1}',
                    'name': f'Variable {s1}',
                    'role': 'predictor',
                    'type': 'signal',
                    'domain': domain,
                    'status': 'UNBOUND',
                    'candidate_values': [s1],
                    'value': None,
                    'binding': None,
                    'binding_source': None,
                },
                {
                    'id': f'var_{s2}',
                    'variable_id': f'var_{s2}',
                    'name': f'Variable {s2}',
                    'role': 'outcome',
                    'type': 'signal',
                    'domain': domain,
                    'status': 'UNBOUND',
                    'candidate_values': [s2],
                    'value': None,
                    'binding': None,
                    'binding_source': None,
                }
            ]
            relational = [{
                'source_var': f'var_{s1}',
                'target_var': f'var_{s2}',
                'relation_type': 'CORRELATED',
                'description': f'Hypothesized coupling between {s1} and {s2}'
            }]

        thesis_doc = {
            'thesis_id': thesis_id,
            'hypothesis_template': template,
            'investigation_status': 'OPEN',
            'open_variables': open_vars,
            'relational_hypotheses': relational,
            'conditions': ['controlling for sensor variance'],
            'required_signals': [],
            'opportunity_ref': opp_id,
            'resolution': 'DEFERRED_TO_SYNAPSE',
            'provenance': {
                'discovery_opportunity': opp_id,
                'opportunity_type': opp_type,
                'cycle_id': c_id,
                'generator_model': 'pyhok-discovery-engine-v1',
                'novelty_score': opportunity.get('novelty_score', 0.8),
                'information_gain_score': opportunity.get('information_gain_score', 0.7),
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
        }
        return thesis_doc
