"""``DebateRunner`` -- the judge-vs-human-proxy convergence loop.

Drives repeated single-shot ``LMEngine.generate()`` calls (no engine/transport changes
-- the transcript is re-serialized into each new prompt by the caller, per
``DebateTranscript.as_text()``). Reuses ``vejudge.core.judge.parse.parse_json_object``
and ``vejudge.core.judge.validate.validate_judge_output`` unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ....lm_engine.lm_template import LMEngine
from ...judge.parse import parse_json_object
from ...judge.validate import validate_judge_output
from ...prompts import d1_judge_debate, d2_human_proxy_debate
from ...prompts.spec import PromptSpec
from .retrieval import find_similar_human_note
from .disagreement import build_disagreement_profile
from .schema import (
    DebateTranscript,
    DebateTurn,
    DebateVerdict,
    extract_original_score,
    normalize_failure_modes,
    render_reasoning_trace,
)


@dataclass
class DebateConfig:
    epsilon: float = 0.25
    max_rounds: int = 4
    retrieval_enabled: bool = True
    # Opt-in when a scalar human anchor or unreduced raw ratings are available. A
    # scalar target requires closing its gap; raw ratings ground the proxy while
    # preserving disagreement and therefore retain score-stability convergence.
    ground_in_human_labels: bool = False
    # Per-item real human aggregate score (set via dataclasses.replace() per call, the
    # same way metric_id is already resolved per item by the caller) — None means "no
    # usable human anchor for this item," which silently falls back to blind debate
    # behavior even if ground_in_human_labels is True.
    human_anchor_score: Optional[float] = None
    # Raw per-rater scores for aggregation_method="none". These ground the human
    # proxy without inventing a consensus target. Numeric convergence therefore uses
    # ordinary score stability while the proxy continues to see the full disagreement.
    human_raw_scores: Optional[list[float]] = None

    def __post_init__(self) -> None:
        self.max_rounds = min(6, max(1, int(self.max_rounds)))


def _semantic_signature(parsed: dict[str, Any]) -> tuple[str, ...]:
    summary = parsed.get("semantic_summary")
    if not isinstance(summary, dict):
        return ()
    text = " ".join(
        str(value) if not isinstance(value, list) else " ".join(map(str, value))
        for value in summary.values()
    ).lower()
    return tuple(sorted({token.strip(".,:;!?()[]{}\"'") for token in text.split() if token}))


def _same_semantic_finding(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    if not a or not b:
        return False
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(1, len(sa | sb)) >= 0.9


def _repeating_score_cycle(scores: list[float]) -> bool:
    """Detect any immediately repeated score cycle, not only A-B-A-B.

    A three-position cycle (A-B-C-A-B-C) appeared in a live grounded debate and
    previously ran until the hard round cap because the old check only recognized a
    period of two.  Requiring two complete adjacent periods avoids treating ordinary
    one-off score revisions as oscillation.
    """
    for period in range(2, len(scores) // 2 + 1):
        cycle = scores[-period:]
        if len(set(cycle)) > 1 and scores[-2 * period:-period] == cycle:
            return True
    return False


class DebateTurnRunner:
    """Runs one turn: build prompt (given transcript so far) -> engine.generate ->
    parse -> validate. Mirrors ``Judge.run``'s shape exactly, including never letting
    an engine exception escape a single turn."""

    def __init__(self, engine: LMEngine, *, model: Optional[str] = None) -> None:
        self.engine = engine
        self.model = model

    def run_turn(
        self,
        *,
        role: str,
        build: Callable[..., PromptSpec],
        build_kwargs: dict[str, Any],
        round_no: int,
    ) -> DebateTurn:
        spec = build(**build_kwargs)

        try:
            out = self.engine.generate(spec.user, system=spec.system, model=self.model)
        except Exception as e:  # noqa: BLE001 -- recorded, never raised out of one turn
            return DebateTurn(
                round=round_no,
                role=role,
                prompt_version=spec.version,
                prompt_system=spec.system,
                prompt_user=spec.user,
                raw_content="",
                parsed=None,
                validation_flags=["engine_error"],
                valid=False,
                model=self.model,
                error=str(e),
            )

        content = out.get("content") or ""
        try:
            parsed = parse_json_object(content)
        except (ValueError, TypeError):
            parsed = None

        validation = validate_judge_output(
            parsed, required_fields=[
                key for key in spec.schema if key not in spec.optional_fields
            ],
        )

        failure_modes: list[str] = []
        flags = list(validation.flags)
        if role == "human_proxy" and parsed:
            known, unknown = normalize_failure_modes(parsed.get("cited_failure_modes"))
            failure_modes = known
            flags.extend(f"unknown_failure_mode:{tag}" for tag in unknown)

        return DebateTurn(
            round=round_no,
            role=role,
            prompt_version=spec.version,
            prompt_system=spec.system,
            prompt_user=spec.user,
            raw_content=content,
            parsed=parsed,
            validation_flags=flags,
            valid=validation.ok,
            model=out.get("model"),
            promptTokens=out.get("promptTokens"),
            completionTokens=out.get("completionTokens"),
            totalTokens=out.get("totalTokens"),
            failure_modes=failure_modes,
        )


class DebateRunner:
    """Runs a bounded judge-vs-human-proxy debate for one (item, metric) pair, starting
    from a pre-existing ``Judge.run()`` output -- the debate never re-derives round-0."""

    def __init__(
        self,
        *,
        metric_id: str,
        judge_engine: LMEngine,
        proxy_engine: LMEngine,
        judge_model: Optional[str] = None,
        proxy_model: Optional[str] = None,
        config: Optional[DebateConfig] = None,
    ) -> None:
        self.metric_id = metric_id
        self.config = config or DebateConfig()
        self._judge_runner = DebateTurnRunner(judge_engine, model=judge_model)
        self._proxy_runner = DebateTurnRunner(proxy_engine, model=proxy_model)

    def run(self, sample: dict[str, Any], original_output: dict[str, Any]) -> DebateVerdict:
        item_id = sample.get("item_id") or (
            f"{sample.get('project', '')}::{sample.get('prompt_idx', '')}::{sample.get('model', '')}"
        )
        initial_score = extract_original_score(original_output, self.metric_id)
        # Grounded only when both opted in AND a real anchor actually exists for this
        # item -- the second half is what makes per-item fallback automatic (an item
        # with no human data behaves exactly like today, no special-cased branch).
        raw_grounded = bool(self.config.human_raw_scores)
        disagreement_profile = build_disagreement_profile(self.config.human_raw_scores or [])
        grounded = bool(
            self.config.ground_in_human_labels
            and (self.config.human_anchor_score is not None or raw_grounded)
        )

        note = None
        if self.config.retrieval_enabled:
            note = find_similar_human_note(sample=sample, metric_id=self.metric_id)
        retrieved_note_text = note.text if note else None

        transcript = DebateTranscript(
            item_id=item_id,
            metric_id=self.metric_id,
            epsilon=self.config.epsilon,
            max_rounds=self.config.max_rounds,
            judge_agent_model=self._judge_runner.model,
            human_proxy_model=self._proxy_runner.model,
            initial_judge_result=original_output,
            created_at=datetime.now(timezone.utc).isoformat(),
            human_disagreement_profile=disagreement_profile,
        )

        prev_score = initial_score
        converged = False
        convergence_reason = ""
        rounds_run = 0
        score_history: list[float] = []
        previous_semantic: tuple[str, ...] = ()
        semantic_stale_rounds = 0

        for round_no in range(1, self.config.max_rounds + 1):
            rounds_run = round_no

            proxy_turn = self._proxy_runner.run_turn(
                role="human_proxy",
                build=d2_human_proxy_debate.build,
                build_kwargs=dict(
                    sample=sample,
                    metric_id=self.metric_id,
                    original_output=original_output,
                    transcript_text=transcript.as_text(),
                    round_no=round_no,
                    retrieved_note=retrieved_note_text,
                    real_human_score=(self.config.human_anchor_score if grounded else None),
                    human_disagreement_profile=(disagreement_profile if grounded else None),
                ),
                round_no=round_no,
            )
            if note is not None and proxy_turn.error is None:
                proxy_turn.retrieval_used = True
                proxy_turn.retrieved_note = note
            transcript.turns.append(proxy_turn)

            judge_turn = self._judge_runner.run_turn(
                role="judge",
                build=d1_judge_debate.build,
                build_kwargs=dict(
                    sample=sample,
                    metric_id=self.metric_id,
                    original_output=original_output,
                    transcript_text=transcript.as_text(),
                    round_no=round_no,
                ),
                round_no=round_no,
            )
            transcript.turns.append(judge_turn)

            if not judge_turn.valid or judge_turn.parsed is None:
                convergence_reason = "invalid_turn"
                break

            new_score = judge_turn.parsed.get("score_1_to_5")
            if not isinstance(new_score, (int, float)) or isinstance(new_score, bool):
                convergence_reason = "invalid_turn"
                break
            new_score = float(new_score)
            score_history.append(new_score)

            current_semantic = _semantic_signature(judge_turn.parsed)
            if _same_semantic_finding(previous_semantic, current_semantic):
                semantic_stale_rounds += 1
            else:
                semantic_stale_rounds = 0
            if current_semantic:
                previous_semantic = current_semantic

            if _repeating_score_cycle(score_history):
                convergence_reason = "oscillation_detected"
                converged = False
                prev_score = initial_score
                break

            # Grounded: self-stability alone is NOT enough to declare convergence --
            # that's exactly the reported failure mode (a stubborn, self-consistent,
            # but factually wrong judge). Only closing the gap to the real human
            # anchor counts; hitting max_rounds without doing so still ends up
            # converged=False, convergence_reason="max_rounds", same shape as today.
            if grounded and self.config.human_anchor_score is not None:
                if abs(new_score - self.config.human_anchor_score) < self.config.epsilon:
                    prev_score = new_score
                    converged = True
                    convergence_reason = "epsilon_human"
                    break
            elif prev_score is not None and abs(new_score - prev_score) < self.config.epsilon:
                prev_score = new_score
                converged = True
                convergence_reason = "epsilon_raw_grounded" if grounded else "epsilon"
                break

            if semantic_stale_rounds >= 2:
                prev_score = new_score
                converged = True
                convergence_reason = "semantic_stable"
                break

            prev_score = new_score
        else:
            convergence_reason = "max_rounds"

        transcript.rounds_run = rounds_run
        transcript.converged = converged
        transcript.convergence_reason = convergence_reason
        transcript.grounded = grounded
        transcript.judge_agent_prompt_version = d1_judge_debate.VERSION
        transcript.human_proxy_prompt_version = d2_human_proxy_debate.VERSION

        flags: list[str] = []
        if convergence_reason:
            flags.append(convergence_reason)

        # Last *valid* judge turn, not just the most recent one -- an invalid final
        # round (e.g. unparseable content) must not discard an earlier valid score.
        final_score: Optional[float] = None
        for t in reversed(transcript.turns):
            if t.role == "judge" and t.valid and t.parsed:
                score = t.parsed.get("score_1_to_5")
                if isinstance(score, (int, float)) and not isinstance(score, bool):
                    final_score = float(score)
                break

        if convergence_reason == "oscillation_detected":
            final_score = initial_score

        if all(t.error for t in transcript.turns):
            convergence_reason = "all_turns_failed"
            transcript.convergence_reason = convergence_reason
            flags = ["all_turns_failed"]
            final_score = None

        score_delta = (
            (final_score - initial_score)
            if final_score is not None and initial_score is not None
            else None
        )

        failure_mode_summary: dict[str, int] = {}
        for t in transcript.turns:
            for mode in t.failure_modes:
                failure_mode_summary[mode] = failure_mode_summary.get(mode, 0) + 1

        reasoning_trace = render_reasoning_trace(transcript, original_output)

        return DebateVerdict(
            item_id=item_id,
            metric_id=self.metric_id,
            initial_score=initial_score,
            final_score=final_score,
            score_delta=score_delta,
            converged=converged,
            rounds_run=rounds_run,
            flags=flags,
            reasoning_trace=reasoning_trace,
            failure_mode_summary=failure_mode_summary,
            transcript=transcript,
            grounded=grounded,
            human_disagreement_profile=disagreement_profile,
        )
