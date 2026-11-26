from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ProviderResult:
    text: str                      
    model_version: str            
    stop_reason: str = ""
    usage: dict = field(default_factory=dict)


class ProviderError(RuntimeError):
    """Raised for failures that should be logged and skipped (refusal, truncation, API error)."""


class Provider:
    name = "base"

    def with_cfg(self, cfg: dict) -> "Provider":
        return self

    def complete(self, system: str, user: str, schema: dict) -> ProviderResult:  # pragma: no cover
        raise NotImplementedError


class AnthropicProvider(Provider):
    name = "anthropic"
    FALLBACK_BETA = "server-side-fallback-2026-07-01"
    FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-2", "claude-fable-5-1"}

    def __init__(self, cfg: dict):
        import anthropic  
        self._anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.cfg = cfg

    def with_cfg(self, cfg: dict) -> "AnthropicProvider":
        import copy
        other = copy.copy(self)
        other.cfg = cfg
        return other

    def _params(self, system: str, user: str, schema: dict) -> dict:
        return dict(
            model=self.cfg["model"],
            max_tokens=self.cfg["max_tokens"],
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.cfg["effort"], "format": {"type": "json_schema", "schema": schema}},
        )

    def complete(self, system: str, user: str, schema: dict) -> ProviderResult:
        a = self._anthropic
        params = self._params(system, user, schema)
        try:
            if self.cfg.get("server_side_fallback") and self.cfg["model"] in self.FALLBACK_MODELS:
                resp = self.client.beta.messages.create(betas=[self.FALLBACK_BETA], fallbacks="default", **params)
            else:
                resp = self.client.messages.create(**params)
        except a.AuthenticationError as e:
            raise SystemExit(f"Anthropic authentication failed ({e.status_code}); set ANTHROPIC_API_KEY") from e
        except a.BadRequestError as e:
            raise ProviderError(f"bad request: {e.message}") from e
        except a.RateLimitError as e:
            raise ProviderError("rate limited after SDK retries") from e
        except a.APIStatusError as e:
            raise ProviderError(f"API error {e.status_code}: {e.message}") from e
        except a.APIConnectionError as e:
            raise ProviderError(f"connection error: {e}") from e
        if resp.stop_reason == "refusal":
            cat = getattr(getattr(resp, "stop_details", None), "category", None)
            raise ProviderError(f"refusal (category {cat})")
        if resp.stop_reason == "max_tokens":
            raise ProviderError("answer truncated at max_tokens")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        u = resp.usage
        usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                 "request_id": getattr(resp, "_request_id", "") or ""}
        return ProviderResult(text=text, model_version=resp.model, stop_reason=resp.stop_reason, usage=usage)

    def count_tokens(self, system: str, user: str, schema: dict) -> int:
        p = self._params(system, user, schema)
        p.pop("max_tokens")
        p.pop("output_config")
        return self.client.messages.count_tokens(**p).input_tokens


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, cfg: dict | None = None, n: int = 2, responses: list[str] | None = None):
        self.n, self.responses, self.calls = n, list(responses or []), 0

    def complete(self, system: str, user: str, schema: dict) -> ProviderResult:
        self.calls += 1
        if self.responses:
            text = self.responses.pop(0)
        else:
            ids = schema["properties"]["links"]["items"]["properties"]["mitigation_id"].get("enum", [])
            links = [{"mitigation_id": i, "confidence": "medium", "rationale": "Fake rationale."} for i in ids[: self.n]]
            text = json.dumps({"links": links, "issues": []})
        return ProviderResult(text=text, model_version="fake-model-1", stop_reason="end_turn",
                              usage={"input_tokens": len(system + user) // 4, "output_tokens": len(text) // 4})


def get_provider(cfg: dict) -> Provider:
    if cfg["provider"] == "anthropic":
        return AnthropicProvider(cfg)
    if cfg["provider"] == "fake":
        return FakeProvider(cfg)
    raise SystemExit(f"unknown provider {cfg['provider']!r} (implemented: anthropic, fake)")
