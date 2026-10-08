"""Single-attempt durable model slots with a shared, reserved evaluation budget."""
from pathlib import Path
import hashlib
import json

from .artifacts import digest, save_json


class CallFailure(RuntimeError):
    pass


class BudgetExhausted(RuntimeError):
    pass


class ProviderStopped(RuntimeError):
    pass


class DurableCalls:
    """Sequential calls; failed and interrupted slots are never resampled on resume."""
    def __init__(self, directory, engine_factory, *, identity, max_calls=600,
                 max_completion_tokens=768000, reserve_calls=0, reserve_tokens=0):
        self.directory = Path(directory)
        self.engine_factory, self.identity = engine_factory, identity
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "budget.json"
        limits = {"max_calls": max_calls, "max_completion_tokens": max_completion_tokens,
                  "reserve_calls": reserve_calls, "reserve_tokens": reserve_tokens,
                  "identity": identity}
        if not 0 <= reserve_calls <= max_calls or not 0 <= reserve_tokens <= max_completion_tokens:
            raise ValueError("Invalid final evaluation reservation")
        if self.path.exists():
            self.budget = json.loads(self.path.read_text())
            if self.budget["limits"] != limits:
                raise ValueError("Changed call protocol on resume")
        else:
            self.budget = {"limits": limits, "calls": 0, "completion_tokens_or_reserved": 0,
                           "input_tokens": 0, "consecutive_errors": 0, "stopped": None}
            save_json(self.path, self.budget)

    def call(self, stage, payload, schema, *, template, media=(), slot="0", final=False, max_tokens=2048):
        media_identity = [{"type": m["type"], "sha256": hashlib.sha256(Path(m["path"]).read_bytes()).hexdigest()}
                          if m["type"] == "image" else m for m in media]
        key = digest([self.identity, stage, payload, schema, template, media_identity, slot, max_tokens])
        path = self.directory / "jobs" / (key + ".json")
        if path.exists():
            row = json.loads(path.read_text())
            if row["outcome"] != "completed":
                raise CallFailure(f"Retained {row['outcome']} slot {key}")
            return row["parsed"], key
        if self.budget["stopped"]:
            raise ProviderStopped(self.budget["stopped"])
        limits = self.budget["limits"]
        call_limit = limits["max_calls"] - (0 if final else limits["reserve_calls"])
        token_limit = limits["max_completion_tokens"] - (0 if final else limits["reserve_tokens"])
        if self.budget["calls"] + 1 > call_limit or self.budget["completion_tokens_or_reserved"] + max_tokens > token_limit:
            raise BudgetExhausted("Call or completion-token allowance exhausted; final comparison is reserved")
        # Reserve durably before contacting the provider. A crash is charged conservatively.
        self.budget["calls"] += 1
        self.budget["completion_tokens_or_reserved"] += max_tokens
        save_json(self.path, self.budget)
        row = {"execution_ref": key, "stage": stage, "slot": slot, "outcome": "interrupted",
               "payload": payload, "max_tokens": max_tokens, "media_identity": media_identity}
        save_json(path, row)
        try:
            engine = self.engine_factory(max_tokens)
            response = engine.generate(template + "\nINPUT_JSON: " + json.dumps(payload),
                                       media_inputs=list(media), schema=schema, strict_schema=True)
        except Exception as exc:
            # Exceptions contain diagnostics only; credentials are never stored by this layer.
            message = str(exc)
            row.update(outcome="transport_error", error=message)
            self.budget["consecutive_errors"] += 1
            rejected = any(word in message.lower() for word in
                           ("400", "401", "403", "404", "model_not_found", "invalid_api_key", "permission"))
            if rejected or self.budget["consecutive_errors"] >= 3:
                self.budget["stopped"] = "Provider rejected the request" if rejected else "Three consecutive transport failures"
            save_json(path, row)
            save_json(self.path, self.budget)
            if self.budget["stopped"]:
                raise ProviderStopped(self.budget["stopped"]) from exc
            raise CallFailure(f"Transport failure in slot {key}: {message}") from exc
        self.budget["consecutive_errors"] = 0
        completion = int(response.get("completionTokens", response.get("completion_tokens", max_tokens)) or 0)
        self.budget["completion_tokens_or_reserved"] += completion - max_tokens
        self.budget["input_tokens"] += int(response.get("promptTokens", response.get("prompt_tokens", 0)) or 0)
        row["response"] = response
        parsed = response.get("parsed")
        row.update(outcome="completed" if isinstance(parsed, dict) and response.get("finishReason") in (None, "stop") else "invalid",
                   parsed=parsed)
        save_json(path, row)
        save_json(self.path, self.budget)
        if row["outcome"] != "completed":
            raise CallFailure(f"Invalid model response in slot {key}")
        return parsed, key
