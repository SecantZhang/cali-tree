import sys
from types import ModuleType

from vejudge.core.calibration.textgrad_adapter import textgrad_update


class _Engine:
    model = "optimizer-model"

    def generate(self, prompt, system=None):
        return {
            "content": f"updated: {prompt}",
            "promptTokens": 2,
            "completionTokens": 3,
            "totalTokens": 5,
        }


def test_official_textgrad_adapter_forwards_usage_and_preserves_constraints(monkeypatch, tmp_path):
    textgrad = ModuleType("textgrad")
    engine_module = ModuleType("textgrad.engine")

    class EngineLM:
        pass

    class Variable:
        def __init__(self, value, **_kwargs):
            self.value = value
            self.gradients = set()

    class TGD:
        seen_constraints = None

        def __init__(self, *, parameters, engine, constraints):
            self.parameters = parameters
            self.engine = engine
            TGD.seen_constraints = constraints

        def step(self):
            self.parameters[0].value = self.engine("rewrite")

    engine_module.EngineLM = EngineLM
    textgrad.Variable = Variable
    textgrad.TGD = TGD
    monkeypatch.setitem(sys.modules, "textgrad", textgrad)
    monkeypatch.setitem(sys.modules, "textgrad.engine", engine_module)
    usage = []
    updated = textgrad_update(
        "rubric", "wrong label", engine=_Engine(), usage_cb=usage.append, log_dir=tmp_path
    )
    assert updated == "updated: rewrite"
    assert usage[0]["completionTokens"] == 3
    assert any("no, partial, yes" in value for value in TGD.seen_constraints)
    assert str(tmp_path) == __import__("os").environ["TEXTGRAD_LOG_DIR"]
