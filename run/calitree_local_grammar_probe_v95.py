"""Freeze a separate local observation probe with native JSON token constraints."""
import argparse
from pathlib import Path

from critical.lm_engine.local_qwen_grammar_v95 import LocalQwenGrammarEngine
from critical.core.decision.artifacts import digest
from critical.core.decision import local_rubric_evidence_v94 as facts
from run import calitree_local_observer_v94 as probe


def prepare(out):
    profile = {'decoder': 'native-json-schema-prefix', 'schema_ref': digest(facts.schema()),
               'extra_requirements': {'lm-format-enforcer': '0.11.3'},
               'prior_probe': 'v94 schema failures retained; this is a new decoding profile, not response repair.'}
    probe.prepare(out, engine_type=LocalQwenGrammarEngine, extra_profile=profile,
                  extra_sources=(Path(__file__), probe.ROOT/'critical/lm_engine/local_qwen_grammar_v95.py'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--prepare', action='store_true'); p.add_argument('--collect', action='store_true'); a = p.parse_args()
    if a.prepare == a.collect:
        p.error('Choose exactly one of --prepare / --collect')
    if a.prepare:
        prepare(a.output_dir.resolve())
    else:
        probe.collect(a.output_dir.resolve(), engine_type=LocalQwenGrammarEngine)
