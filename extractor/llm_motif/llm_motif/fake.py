
from __future__ import annotations
import json
from llm_mitigation.providers import Provider, ProviderResult, get_provider as _get_provider


class FakeMotifProvider(Provider):
    name = "fake"
    def __init__(self, cfg: dict | None = None, responses: list[str] | None = None):
        self.responses, self.calls = list(responses or []), 0

    @staticmethod
    def _pick(enum: list[str], preferred: list[str]) -> str:
        return next((p for p in preferred if p in enum), enum[0])

    def complete(self, system: str, user: str, schema: dict) -> ProviderResult:
        self.calls += 1
        if self.responses:
            text = self.responses.pop(0)
        else:
            p = schema["properties"]
            classes = p["elements"]["items"]["properties"]["class"]["enum"]
            data, model, proc = (self._pick(classes, ["Data"]), self._pick(classes, ["LLM", "Model"]),
                                 self._pick(classes, ["Infer", "Process"]))
            motif = "support" in p
            ids = ["m1", "m2", "m3", "m4"] if motif else ["e1", "e2", "e3", "e4"]
            elements = [{"id": ids[0], "class": data}, {"id": ids[1], "class": model}, {"id": ids[2], "class": proc},
                        {"id": ids[3], "class": data}]
            flows = [{"from": ids[2], "relation": "uses", "to": ids[0]}, {"from": ids[2], "relation": "uses", "to": ids[1]},
                     {"from": ids[2], "relation": "produces", "to": ids[3]}]
            if motif:
                for e, label in zip(elements, ["input data", "model", "inference", "output data"]):
                    e["label"] = label
                ans = {"name": "Fake motif", "description": "Fake description.", "risk_id": p["risk_id"]["enum"][0],
                       "elements": elements, "flows": flows, "contexts": [], "manifest_condition": ids[3],
                       "support": list(p["support"]["items"]["enum"]), "confidence": "medium", "issues": []}
            else:
                for e, label in zip(elements, ["input", "model", "inference", "output"]):
                    e.update({"label": label, "evidence": ""})
                risk_enum = p["risks"]["items"]["properties"]["risk_id"]["enum"]
                ans = {"elements": elements, "flows": flows, "contexts": [], "failure_point": ids[3],
                       "risks": [] if risk_enum == ["none"] else
                       [{"risk_id": risk_enum[0], "confidence": "medium", "rationale": "Fake rationale."}],
                       "confidence": "medium", "issues": []}
            text = json.dumps(ans)
        return ProviderResult(text=text, model_version="fake-model-1", stop_reason="end_turn",
                              usage={"input_tokens": len(system + user) // 4, "output_tokens": len(text) // 4})


def get_provider(cfg: dict) -> Provider:
    if cfg["provider"] == "fake":
        return FakeMotifProvider(cfg)
    return _get_provider(cfg)   