"""Observe returned provider usage without changing SDK arguments or RAG policy."""
import math
from contextlib import contextmanager


def _field(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def usage_from_response(response):
    usage = _field(response, "usage")
    def count(*keys):
        for key in keys:
            value = _field(usage, key)
            if value is not None:
                return value if type(value) is int and value >= 0 else None
        return None
    return {"input_tokens": count("prompt_tokens", "input_tokens"),
            "output_tokens": count("completion_tokens", "output_tokens")}


@contextmanager
def observe_provider(workflow):
    """Exclusive serial workflow only. Record each SDK attempt, including failures.

    Replace only the completions object, restore on exit; credentials and request
    bodies are never serialized. The original method returns the original object.
    """
    events, restored, seen = [], [], set()
    try:
        for name in ("grader", "generator", "rewriter"):
            component = getattr(workflow, name, None)
            client = getattr(component, "client", None)
            chat = getattr(client, "chat", None)
            completions = getattr(chat, "completions", None)
            if completions is None or id(chat) in seen:
                continue
            seen.add(id(chat))
            create = getattr(completions, "create", None)
            if not callable(create):
                continue
            class Observed:
                def __init__(self, inner, method):
                    self.inner, self.method = inner, method

                def __getattr__(self, key):
                    return getattr(self.inner, key)

                def create(self, *args, **kwargs):
                    event = {"input_tokens": None, "output_tokens": None, "completed": False}
                    events.append(event)
                    try:
                        result = self.method(*args, **kwargs)
                        event.update(usage_from_response(result), completed=True)
                        return result
                    except Exception as exc:
                        event["exception_type"] = type(exc).__name__
                        raise
            proxy = Observed(completions, create)
            # Installation failure is explicit, never silently treated as full observation.
            restored.append((chat, completions))
            chat.completions = proxy
        yield events
    finally:
        for chat, original in reversed(restored):
            chat.completions = original


def summarize_usage(events, expected_calls, pricing=None):
    complete_inventory = type(expected_calls) is int and expected_calls >= 0 and len(events) == expected_calls
    out = {"attempt_count": len(events), "expected_attempt_count": expected_calls,
           "inventory_complete": complete_inventory, "attempts": events}
    for key in ("input_tokens", "output_tokens"):
        values = [e[key] for e in events if e[key] is not None]
        out[key] = sum(values) if complete_inventory and len(values) == len(events) and events else None
        out[key + "_observed_sum"] = sum(values) if values else None
        out[key + "_observed_attempts"] = len(values)
        out[key + "_observation_ratio"] = len(values) / expected_calls if type(expected_calls) is int and expected_calls > 0 else None
    out["estimated_cost"] = None
    out["currency"] = None
    if pricing is not None:
        required = {"input_per_million", "output_per_million", "currency", "source", "effective_at"}
        if not isinstance(pricing, dict) or set(pricing) != required:
            raise ValueError("pricing requires explicit rates, currency, source and date")
        for key in ("input_per_million", "output_per_million"):
            val = pricing[key]
            if type(val) not in (int, float) or not math.isfinite(val) or val < 0:
                raise ValueError("invalid price")
        if any(not isinstance(pricing[k], str) or not pricing[k].strip() for k in ("currency", "source", "effective_at")):
            raise ValueError("invalid pricing provenance")
        out["currency"] = pricing["currency"]
        if out["input_tokens"] is not None and out["output_tokens"] is not None:
            out["estimated_cost"] = (out["input_tokens"] * pricing["input_per_million"] + out["output_tokens"] * pricing["output_per_million"]) / 1_000_000
    out["pricing"] = pricing
    return out


def usage_report(observations):
    output = {}
    for key in ("input_tokens", "output_tokens", "estimated_cost"):
        values, missing, currencies = {}, [], set()
        for obs in observations:
            usage = obs.get("extensions", {}).get("provider_usage", {})
            value = (usage.get(key) if key == "estimated_cost" else obs["measurements"][key])
            if value is None:
                missing.append(obs["case_id"])
            else:
                values[obs["case_id"]] = value
            if key == "estimated_cost" and value is not None:
                currencies.add(usage.get("currency"))
        currency_ok = key != "estimated_cost" or (len(currencies) == 1 and None not in currencies)
        output[key] = {"observed_sum": sum(values.values()) if values and currency_ok else None,
                       "full_sum": sum(values.values()) if values and not missing and currency_ok else None,
                       "observed_count": len(values), "total_count": len(observations),
                       "observation_ratio": len(values) / len(observations) if observations else None,
                       "missing_case_ids": sorted(missing), "currencies": sorted(c for c in currencies if c)}
    return output
