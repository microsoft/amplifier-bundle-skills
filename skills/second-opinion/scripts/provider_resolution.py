"""Stdlib-only, deterministic provider/model selection for second-opinion."""

from __future__ import annotations

from collections import Counter
import re
import unicodedata
from typing import Any


class ResolutionError(Exception):
    """A non-sensitive error suitable for structured output."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def _fail(code: str, message: str) -> None:
    raise ResolutionError(code, message)


def concrete_model(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if (not value or any(char.isspace() for char in value) or value == "-"
            or any(char in value for char in "*?[]{}$")
            or (value.startswith("<") and value.endswith(">"))
            or value.casefold() in {"model", "default", "placeholder", "none", "null", "unknown"}):
        return None
    return value


def _fail_schema() -> None:
    _fail("malformed_schema", "Provider configuration has an invalid schema.")


def _string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        _fail_schema()
    return value.strip()


def _priority(value: Any) -> tuple[int, ...]:
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+)*", value.strip()):
        _fail_schema()
    return tuple(int(part) for part in value.strip().split("."))


def _normal(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_VERSION_RE = re.compile(r"\d+(?:[.-]\d+)*")
_SNAPSHOT_RE = re.compile(r"[-_/](?:19|20)\d{2}(?:-\d{2}-\d{2}|\d{4})$")
_REQUEST_NOISE = {"a", "an", "ask", "have", "please", "the", "to", "use", "with", "reviewer"}


def _parts(value: str, *, phrase: bool = False) -> tuple[Counter[str], tuple[int, ...] | None, bool]:
    """Return word atoms, normalized dotted/hyphenated version, and latest flag."""
    text = _SNAPSHOT_RE.sub("", _normal(value))
    words = Counter(_WORD_RE.findall(text))
    if phrase:
        words.subtract(_REQUEST_NOISE)
        words = Counter({word: count for word, count in words.items() if count > 0})
        # In "have nova 6.1 review", review is grammatical framing; in
        # "latest review" it is the requested model family and is retained.
        if words.get("review") and "latest" not in words and "newest" not in words and len(words) > 1:
            words["review"] -= 1
            if not words["review"]:
                del words["review"]
    versions = _VERSION_RE.findall(text)
    version = tuple(int(part) for part in re.split(r"[.-]", versions[-1])) if versions else None
    return words, version, "latest" in words or "newest" in words


def _normal_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict) or type(item.get("enabled")) is not bool:
        _fail_schema()
    name = _string(item, "name")
    active = name.startswith("★ ")
    if active:
        name = name[2:].strip()
    if not name or not isinstance(item.get("behaviors"), list) or any(not isinstance(x, str) for x in item["behaviors"]):
        _fail_schema()
    summary = item.get("config_summary")
    if not isinstance(summary, dict) or "model" not in summary:
        _fail_schema()
    raw_model = summary["model"]
    default = None if raw_model in (None, "-") else concrete_model(raw_model)
    if raw_model not in (None, "-") and default is None:
        _fail_schema()
    return {"id": name, "enabled": item["enabled"], "provider_type": _string(summary, "type"),
            "default_model": default, "scope": _string(summary, "scope"), "priority": _priority(summary.get("priority")),
            "active": active}


def normalize_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        _fail_schema()
    result = [_normal_item(item) for item in items]
    if len({_normal(item["id"]) for item in result}) != len(result):
        _fail("duplicate_id", "Provider configuration contains duplicate provider ids.")
    return result


def normalize_inventories(inventories: Any, candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    if inventories is None:
        return {}
    if not isinstance(inventories, dict):
        _fail("invalid_inventory", "Model inventory has an invalid schema.")
    ids = {_normal(candidate["id"]): candidate["id"] for candidate in candidates}
    result: dict[str, list[dict[str, str]]] = {}
    for provider_id, payload in inventories.items():
        if not isinstance(provider_id, str) or _normal(provider_id) not in ids:
            continue
        models = payload.get("models") if isinstance(payload, dict) else payload
        if not isinstance(models, list):
            _fail("invalid_inventory", "Model inventory has an invalid schema.")
        records, seen = [], set()
        for model in models:
            if isinstance(model, str):
                model_id, source, availability = concrete_model(model), "supplied", "unknown"
            elif isinstance(model, dict):
                model_id = concrete_model(model.get("id"))
                source = model.get("source", "supplied")
                availability = model.get("availability", model.get("available", "unknown"))
            else:
                _fail("invalid_inventory", "Model inventory has an invalid schema.")
            if model_id is None or source not in {"live", "provider_supported", "supplied"}:
                _fail("invalid_inventory", "Model inventory has an invalid schema.")
            if type(availability) is bool:
                availability = "available" if availability else "unavailable"
            if availability not in {"available", "unavailable", "unknown"}:
                _fail("invalid_inventory", "Model inventory has an invalid schema.")
            key = _normal(model_id)
            if key not in seen:
                seen.add(key)
                records.append({"id": model_id, "source": source, "availability": availability})
        result[ids[_normal(provider_id)]] = records
    return result


def _validate(config_id: Any, provider: Any, model: Any) -> tuple[str | None, str | None, str | None]:
    if config_id is not None and provider is not None:
        _fail("invalid_selector", "Specify exactly one provider id or provider type.")
    if config_id is None and provider is None:
        _fail("invalid_selector", "Specify a provider id, provider type, or request phrase.")
    if config_id is not None and (not isinstance(config_id, str) or not config_id.strip()):
        _fail("invalid_selector", "Provider id must be a non-blank string.")
    if provider is not None and (not isinstance(provider, str) or not provider.strip()):
        _fail("invalid_selector", "Provider type must be a non-blank string.")
    checked = concrete_model(model) if model is not None else None
    if model is not None and checked is None:
        _fail("invalid_model", "Model must be a concrete non-blank model name.")
    return config_id.strip() if isinstance(config_id, str) else None, provider.strip() if isinstance(provider, str) else None, checked


def _options(candidates: list[dict[str, Any]], inventories: dict[str, list[dict[str, str]]]) -> list[tuple[dict[str, Any], dict[str, str]]]:
    options = []
    for candidate in candidates:
        models = list(inventories.get(candidate["id"], []))
        if candidate["default_model"] and not any(_normal(entry["id"]) == _normal(candidate["default_model"]) for entry in models):
            models.append({"id": candidate["default_model"], "source": "supplied", "availability": "unknown"})
        options.extend((candidate, entry) for entry in models if entry["availability"] != "unavailable")
    return options


def _rank_model(options: list[tuple[dict[str, Any], dict[str, str]]], requested: str, *, phrase: bool) -> tuple[list[tuple[dict[str, Any], dict[str, str]]], str]:
    exact = [(endpoint, record) for endpoint, record in options if _normal(record["id"]) == _normal(requested)]
    if exact:
        return exact, "model_match"
    words, version, latest = _parts(requested, phrase=phrase)
    family_words = Counter({word: count for word, count in words.items() if word not in {"latest", "newest"}})
    width = max((len(_parts(record["id"])[1] or ()) for _, record in options), default=0)
    decorated = []
    for endpoint, record in options:
        candidate_words, candidate_version, _ = _parts(record["id"])
        if not family_words <= candidate_words:
            continue
        extra = sum((candidate_words - family_words).values())
        snapshot = int(bool(_SNAPSHOT_RE.search(_normal(record["id"]))))
        newer = tuple(-part for part in (candidate_version or ()) + (0,) * (width - len(candidate_version or ())))
        exact_words = candidate_words == family_words
        exact_version = version == candidate_version
        if latest:
            # ``latest nova-6`` means the greatest known version in the 6 series,
            # not the greatest arbitrary nova version.  When the exact requested
            # prefix is absent we still rank a family fallback, but disclose it.
            if candidate_version is None:
                continue
            if version is not None:
                prefix_match = candidate_version[:len(version)] == version
                same_major = candidate_version[0] == version[0]
                fallback_group = 0 if prefix_match else (1 if same_major else 2)
            else:
                fallback_group = 0
            score = (fallback_group, extra, newer, snapshot)
            decorated.append((score, endpoint, record))
        elif version is not None:
            if exact_words and exact_version:
                score = (0, 0, extra, snapshot)
            elif candidate_version is not None:
                same_major = int(candidate_version[0] != version[0])
                padded = max(len(version), len(candidate_version))
                distance = sum(abs((version + (0,) * padded)[i] - (candidate_version + (0,) * padded)[i]) for i in range(padded))
                # Equal-distance compatible versions prefer the newer numeric
                # candidate, never provider-list order.
                score = (1, same_major, distance, newer, extra, snapshot)
            else:
                continue
            decorated.append((score, endpoint, record))
        else:
            # A family shorthand chooses the least-qualified family, its floating
            # alias if present, otherwise its newest known version. Do not make
            # the user resolve a version-only tie by hand.
            score = (extra, 0 if candidate_version is None else 1, newer, snapshot)
            decorated.append((score, endpoint, record))
    if not decorated:
        _fail("no_match", "No configured provider or known model matches the request; obtain a provider inventory or name a configured provider.")
    best_score = min(row[0] for row in decorated)
    substitute = version is not None and best_score[0] != 0
    return [
        (endpoint, record)
        for score, endpoint, record in decorated
        if score == best_score
    ], "family_substitute" if substitute else "model_match"


def _choose(options: list[tuple[dict[str, Any], dict[str, str]]], *, requested: str | None, resolution: str) -> tuple[dict[str, Any], dict[str, str], str]:
    priority = min(endpoint["priority"] for endpoint, _ in options)
    best = [(endpoint, record) for endpoint, record in options if endpoint["priority"] == priority]
    endpoints = {_normal(endpoint["id"]) for endpoint, _ in best}
    if len(endpoints) > 1:
        active = [(endpoint, record) for endpoint, record in best if endpoint["active"]]
        if len({_normal(endpoint["id"]) for endpoint, _ in active}) != 1:
            _fail("ambiguous_provider", "Multiple providers match at the same priority.")
        best = [({**endpoint, "active_tiebreak": True}, record) for endpoint, record in active]
    identities = {_normal(record["id"]) for _, record in best}
    if len(identities) > 1:
        _fail("ambiguous_model", "Multiple equally suitable known models match the request.")
    return best[0][0], best[0][1], resolution


def _result(endpoint: dict[str, Any], record: dict[str, str], resolution: str, *, requested: str | None = None) -> dict[str, Any]:
    verified = record["source"] == "live" and record["availability"] == "available"
    disclosure = []
    if endpoint.get("active_tiebreak"):
        disclosure.append("The active configured provider broke an equal-priority endpoint tie.")
    if resolution not in {"exact_id_default", "provider_default"}:
        disclosure.append("Model selection was inferred from the requested phrase or model.")
    if resolution == "family_substitute":
        disclosure.append("Requested model version was unavailable; a known same-family substitute was selected.")
    if not verified:
        disclosure.append("Model availability is unverified; inventory discovery is not execution proof.")
    return {"ok": True, "provider_id": endpoint["id"], "provider_type": endpoint["provider_type"], "model": record["id"],
            "configured_default_model": endpoint["default_model"], "config_scope": endpoint["scope"], "settings_checked": True,
            "mounted_checked": False, "execution_verified": False, "resolution": resolution,
            "requested_model": requested, "substitute_from": requested if resolution == "family_substitute" else None,
            "model_availability": "available" if verified else "unverified", "inventory_source": record["source"],
            "endpoint_selection": "active_provider_tiebreak" if endpoint.get("active_tiebreak") else "configured_priority",
            "disclosure": disclosure}


def _resolve(candidates: list[dict[str, Any]], inventories: dict[str, list[dict[str, str]]], *, config_id: str | None, provider: str | None, model: str | None) -> dict[str, Any]:
    explicit = config_id is not None
    if explicit:
        selected = [candidate for candidate in candidates if _normal(candidate["id"]) == _normal(config_id or "")]
        if not selected:
            _fail("unknown_id", "The requested provider id is not configured.")
        if not selected[0]["enabled"]:
            _fail("disabled_id", "The requested provider id is disabled.")
    else:
        selected = [candidate for candidate in candidates if candidate["enabled"] and _normal(candidate["provider_type"]) == _normal(provider or "")]
        if not selected:
            _fail("unknown_provider", "No enabled provider has the requested type.")
    if model is None:
        defaults = [(candidate, {"id": candidate["default_model"], "source": "supplied", "availability": "unknown"}) for candidate in selected if candidate["default_model"]]
        if not defaults:
            _fail("missing_model", "The selected provider has no concrete default model.")
        endpoint, record, _ = _choose(defaults, requested=None, resolution="exact_id_default" if explicit else "provider_default")
        return _result(endpoint, record, "exact_id_default" if explicit else "provider_default")
    known = _options(selected, inventories)
    try:
        matches, resolution = _rank_model(known, model, phrase=False)
        endpoint, record, resolution = _choose(matches, requested=model, resolution=resolution)
        return _result(endpoint, record, resolution, requested=model)
    except ResolutionError as error:
        known_ids = {_normal(entry["id"]) for entry in inventories.get(selected[0]["id"], [])}
        if error.code != "no_match" or not explicit or _normal(model) in known_ids:
            raise
        # Only an exact, user-selected configured endpoint may carry an unknown override.
        endpoint = selected[0]
        return _result(endpoint, {"id": model, "source": "supplied", "availability": "unknown"}, "unverified_override", requested=model)


def resolve_provider(items: Any, *, config_id: str | None = None, provider: str | None = None, model: str | None = None, inventories: Any = None) -> dict[str, Any]:
    config_id, provider, model = _validate(config_id, provider, model)
    candidates = normalize_items(items)
    return _resolve(candidates, normalize_inventories(inventories, candidates), config_id=config_id, provider=provider, model=model)


def resolve_request(items: Any, request: Any, *, inventories: Any = None) -> dict[str, Any]:
    if not isinstance(request, str) or not request.strip():
        _fail("invalid_selector", "Reviewer request must be a non-blank string.")
    candidates = normalize_items(items)
    known = normalize_inventories(inventories, candidates)
    exact_id = [candidate for candidate in candidates if _normal(candidate["id"]) == _normal(request)]
    if exact_id:
        return _resolve(candidates, known, config_id=exact_id[0]["id"], provider=None, model=None)
    provider = [candidate for candidate in candidates if _normal(candidate["provider_type"]) == _normal(request)]
    if provider:
        return _resolve(candidates, known, config_id=None, provider=request, model=None)
    matches, resolution = _rank_model(_options([candidate for candidate in candidates if candidate["enabled"]], known), request, phrase=True)
    endpoint, record, resolution = _choose(matches, requested=request, resolution=resolution)
    return _result(endpoint, record, resolution, requested=request)


def _concurrency(value: Any) -> int:
    if type(value) is not int or value <= 0:
        _fail("invalid_concurrency", "Concurrency must be a positive integer.")
    return value


def _reviewer_selector(value: Any) -> tuple[str | None, str | None, str | None, str | None]:
    if not isinstance(value, dict):
        _fail("invalid_reviewer", "Reviewer entry has an invalid selector.")
    keys = set(value)
    if keys in ({"id"}, {"id", "model"}):
        return (*_validate(value["id"], None, value.get("model")), None)
    if keys in ({"provider"}, {"provider", "model"}):
        return (*_validate(None, value["provider"], value.get("model")), None)
    if keys == {"request"} and isinstance(value["request"], str) and value["request"].strip():
        return None, None, None, value["request"]
    _fail("invalid_reviewer", "Reviewer entry has an invalid selector.")


def resolve_reviewers(items: Any, reviewers: Any, *, concurrency: int = 10, inventories: Any = None) -> dict[str, Any]:
    if not isinstance(reviewers, list):
        _fail("invalid_reviewers", "Reviewer list must be a non-empty array.")
    if not reviewers:
        _fail("empty_reviewers", "Reviewer list must not be empty.")
    candidates, concurrency = normalize_items(items), _concurrency(concurrency)
    known = normalize_inventories(inventories, candidates)
    rows, resolved = [], set()
    for index, selector in enumerate(reviewers):
        try:
            config_id, provider, model, request = _reviewer_selector(selector)
            row = resolve_request(items, request, inventories=known) if request is not None else _resolve(candidates, known, config_id=config_id, provider=provider, model=model)
            key = (_normal(row["provider_id"]), _normal(row["model"]))
            if key in resolved:
                _fail("duplicate_reviewer", "Reviewer resolves to a duplicate provider and model.")
        except ResolutionError as error:
            rows.append({"ok": False, "index": index, "code": error.code, "message": error.message})
        else:
            resolved.add(key)
            row["index"] = index
            rows.append(row)
    count = sum(row["ok"] for row in rows)
    return {"ok": count == len(rows), "concurrency": concurrency, "resolved_count": count, "reviewers": rows}
