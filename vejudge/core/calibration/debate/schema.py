"""Data model for a judge-vs-human-proxy calibration debate.

One debate refines a single (item, metric) pair's already-computed judge output
(``vejudge.core.judge.base_judge.Judge.run()``'s result) through bounded rounds of
critique/defense between two LM agents. ``DebateTurn``/``DebateTranscript`` record the
process; ``DebateVerdict`` is the distilled result meant for storage and reuse.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .retrieval import RetrievedNote

# The failure-mode taxonomy is prompt content, owned by core.prompts.d2_human_proxy_debate
# (it's inlined into that persona's system prompt); re-imported here only to normalize
# and count ``cited_failure_modes`` tags against the same fixed vocabulary.
from ...prompts.d2_human_proxy_debate import FAILURE_MODE_TAXONOMY


def normalize_failure_modes(raw: Optional[list[Any]]) -> tuple[list[str], list[str]]:
    """Split cited failure-mode tags into (known, unknown) against the fixed taxonomy.

    Unknown tags are kept out of the counted vocabulary but never silently dropped —
    callers surface them as a validation flag instead.
    """
    known: list[str] = []
    unknown: list[str] = []
    for tag in raw or []:
        key = str(tag).strip().lower().replace(" ", "_").replace("-", "_")
        if key in FAILURE_MODE_TAXONOMY:
            known.append(key)
        elif key:
            unknown.append(key)
    return known, unknown


def extract_original_score(original_output: dict[str, Any], metric_id: str) -> Optional[float]:
    """Pull the anchor score out of a prior ``Judge.run()`` result.

    M6 nests its score under ``overall_av_sync_score``; every other metric uses the
    common ``score_1_to_5`` key (see ``vejudge.core.judge.validate._SCORE_KEYS``).
    """
    parsed = (original_output or {}).get("parsed") or {}
    key = "overall_av_sync_score" if metric_id == "M6" else "score_1_to_5"
    val = parsed.get(key)
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    return None


@dataclass
class DebateTurn:
    round: int
    role: str  # "judge" | "human_proxy"
    prompt_version: str
    prompt_system: Optional[str]
    prompt_user: str
    raw_content: str
    parsed: Optional[dict[str, Any]]
    validation_flags: list[str]
    valid: bool
    model: Optional[str]
    promptTokens: Optional[int] = None
    completionTokens: Optional[int] = None
    totalTokens: Optional[int] = None
    failure_modes: list[str] = field(default_factory=list)
    # Pipeline fact — was a retrieved note actually included in this turn's prompt?
    # Never inferred from the LM's own claims about what it used.
    retrieval_used: bool = False
    retrieved_note: Optional[RetrievedNote] = None
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DebateTurn":
        data = dict(data)
        note = data.get("retrieved_note")
        return cls(
            round=data["round"],
            role=data["role"],
            prompt_version=data["prompt_version"],
            prompt_system=data.get("prompt_system"),
            prompt_user=data["prompt_user"],
            raw_content=data.get("raw_content", ""),
            parsed=data.get("parsed"),
            validation_flags=list(data.get("validation_flags") or []),
            valid=bool(data.get("valid", False)),
            model=data.get("model"),
            promptTokens=data.get("promptTokens"),
            completionTokens=data.get("completionTokens"),
            totalTokens=data.get("totalTokens"),
            failure_modes=list(data.get("failure_modes") or []),
            retrieval_used=bool(data.get("retrieval_used", False)),
            retrieved_note=RetrievedNote(**note) if note else None,
            error=data.get("error"),
        )


@dataclass
class DebateTranscript:
    item_id: str
    metric_id: str
    turns: list[DebateTurn] = field(default_factory=list)
    rounds_run: int = 0
    converged: bool = False
    # "epsilon" | "max_rounds" | "invalid_turn" | "all_turns_failed"
    convergence_reason: str = ""
    epsilon: float = 0.25
    max_rounds: int = 4
    judge_agent_model: Optional[str] = None
    human_proxy_model: Optional[str] = None
    judge_agent_prompt_version: str = ""
    human_proxy_prompt_version: str = ""
    # The pre-existing Judge.run() output this debate starts from — the debate never
    # re-derives round-0 from scratch.
    initial_judge_result: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def as_text(self) -> str:
        """Render prior turns as a compact numbered log for injection into the next
        turn's prompt. Empty transcript (round 1) renders to an empty string."""
        lines: list[str] = []
        for t in self.turns:
            score = (t.parsed or {}).get("score_1_to_5")
            label = "Human-proxy critique" if t.role == "human_proxy" else "Judge response"
            lines.append(f"Round {t.round} -- {label} (score={score}):")
            if t.parsed:
                val = t.parsed.get("reasoning_lines")
                if isinstance(val, list):
                    for line in val:
                        lines.append(f"  - {line}")
            elif t.error:
                lines.append(f"  [turn failed: {t.error}]")
        return "\n".join(lines)

    def last(self, role: str) -> Optional[DebateTurn]:
        for t in reversed(self.turns):
            if t.role == role:
                return t
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DebateTranscript":
        data = dict(data)
        return cls(
            item_id=data["item_id"],
            metric_id=data["metric_id"],
            turns=[DebateTurn.from_dict(t) for t in data.get("turns") or []],
            rounds_run=data.get("rounds_run", 0),
            converged=bool(data.get("converged", False)),
            convergence_reason=data.get("convergence_reason", ""),
            epsilon=data.get("epsilon", 0.25),
            max_rounds=data.get("max_rounds", 4),
            judge_agent_model=data.get("judge_agent_model"),
            human_proxy_model=data.get("human_proxy_model"),
            judge_agent_prompt_version=data.get("judge_agent_prompt_version", ""),
            human_proxy_prompt_version=data.get("human_proxy_prompt_version", ""),
            initial_judge_result=data.get("initial_judge_result") or {},
            created_at=data.get("created_at", ""),
        )


def render_reasoning_trace(
    transcript: DebateTranscript, original_output: dict[str, Any]
) -> str:
    """Deterministic (no extra LM call) text distillation of a debate, meant for
    injection into a later judge prompt or a future corpus-distillation pass."""
    parts: list[str] = []
    orig_lines = ((original_output or {}).get("parsed") or {}).get("reasoning_lines") or []
    if orig_lines:
        parts.append("Original judge rationale: " + " ".join(str(x) for x in orig_lines))

    for t in transcript.turns:
        if not t.parsed:
            continue
        lines = t.parsed.get("reasoning_lines") or []
        if not lines:
            continue
        label = "human-proxy critique" if t.role == "human_proxy" else "judge response"
        parts.append(f"Round {t.round} {label}: " + " ".join(str(x) for x in lines))

    if transcript.converged:
        parts.append(f"Converged after {transcript.rounds_run} round(s).")
    else:
        parts.append(
            f"Did not converge after {transcript.rounds_run} round(s) "
            f"(reason: {transcript.convergence_reason or 'unknown'})."
        )
    return "\n".join(parts)


@dataclass
class DebateVerdict:
    item_id: str
    metric_id: str
    initial_score: Optional[float]
    final_score: Optional[float]  # None only if every judge turn was invalid/errored
    score_delta: Optional[float]
    converged: bool
    rounds_run: int
    flags: list[str]
    reasoning_trace: str
    # Counts per FAILURE_MODE_TAXONOMY key across the transcript — the field a future
    # corpus-distillation pass would group by.
    failure_mode_summary: dict[str, int]
    transcript: DebateTranscript

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DebateVerdict":
        data = dict(data)
        return cls(
            item_id=data["item_id"],
            metric_id=data["metric_id"],
            initial_score=data.get("initial_score"),
            final_score=data.get("final_score"),
            score_delta=data.get("score_delta"),
            converged=bool(data.get("converged", False)),
            rounds_run=data.get("rounds_run", 0),
            flags=list(data.get("flags") or []),
            reasoning_trace=data.get("reasoning_trace", ""),
            failure_mode_summary=dict(data.get("failure_mode_summary") or {}),
            transcript=DebateTranscript.from_dict(data["transcript"]),
        )
