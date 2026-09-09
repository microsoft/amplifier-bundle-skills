"""Tests for discovery-time skill argument completion metadata."""

import json
import os
from pathlib import Path

import pytest

import amplifier_module_tool_skills.discovery as discovery_module
from amplifier_module_tool_skills import SkillsDiscovery
from amplifier_module_tool_skills.discovery import SkillMetadata
from amplifier_module_tool_skills.discovery import discover_skills


def _write_skill(
    tmp_path: Path,
    name: str = "review",
    *,
    argument_hint: str | None = None,
    completion_path: str | None = None,
) -> Path:
    """Create a user-invocable skill and return its directory."""
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    frontmatter = [
        "---",
        f"name: {name}",
        "description: Review a result",
        "user-invocable: true",
    ]
    if argument_hint is not None:
        frontmatter.append(f'argument-hint: "{argument_hint}"')
    if completion_path is not None:
        frontmatter.extend(
            ["metadata:", f"  amplifier.completions: {completion_path}"]
        )
    frontmatter.extend(["---", "Body"])
    (skill_dir / "SKILL.md").write_text("\n".join(frontmatter), encoding="utf-8")
    return skill_dir


def _valid_spec() -> dict:
    return {
        "version": 1,
        "arguments": [
            {"after": [], "values": ["list", "review"]},
            {"after": ["review"], "values": ["accept", "decline", "skip"]},
        ],
    }


def _write_spec(skill_dir: Path, spec: object, path: str = "completions.json") -> None:
    (skill_dir / path).write_text(json.dumps(spec), encoding="utf-8")


def test_discovery_parses_valid_hint_and_completion_sidecar(tmp_path: Path):
    skill_dir = _write_skill(
        tmp_path, argument_hint="[list | review] [action]", completion_path="completions.json"
    )
    spec = _valid_spec()
    _write_spec(skill_dir, spec)

    metadata = discover_skills(tmp_path)["review"]

    assert metadata.argument_hint == "[list | review] [action]"
    assert metadata.completion_spec == spec


def test_discovery_without_completion_metadata_preserves_existing_behavior(tmp_path: Path):
    _write_skill(tmp_path)

    metadata = discover_skills(tmp_path)["review"]

    assert metadata.argument_hint is None
    assert metadata.completion_spec is None


@pytest.mark.parametrize(
    ("spec", "warning"),
    [
        ("not json", "object"),
        ({"version": True, "arguments": []}, "integer 1"),
        (
            {
                "version": 1,
                "arguments": [{"after": [], "values": ["safe", "safe"]}],
            },
            "duplicates",
        ),
        (
            {
                "version": 1,
                "arguments": [{"after": [], "values": ["bad value"]}],
            },
            "safe non-empty tokens",
        ),
        (
            {
                "version": 1,
                "arguments": [{"after": [], "values": ["bad\u001bvalue"]}],
            },
            "safe non-empty tokens",
        ),
        (
            {
                "version": 1,
                "name": "review",
                "arguments": [{"after": [], "values": ["list"]}],
            },
            "keys must be exactly",
        ),
        (
            {
                "version": 1,
                "arguments": [{"after": [], "values": ["list"]}],
                "typo": True,
            },
            "keys must be exactly",
        ),
        (
            {
                "version": 1,
                "arguments": [{"after": [], "values": ["list"], "value": "typo"}],
            },
            "rule keys must be exactly",
        ),
    ],
)
def test_invalid_sidecar_warns_and_does_not_drop_skill(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, spec: object, warning: str
):
    skill_dir = _write_skill(tmp_path, completion_path="completions.json")
    _write_spec(skill_dir, spec)

    with caplog.at_level("WARNING"):
        skills = discover_skills(tmp_path)

    assert "review" in skills
    assert skills["review"].completion_spec is None
    assert warning in caplog.text


def test_malformed_json_sidecar_warns_and_does_not_drop_skill(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    skill_dir = _write_skill(tmp_path, completion_path="completions.json")
    (skill_dir / "completions.json").write_text("{not json", encoding="utf-8")

    with caplog.at_level("WARNING"):
        skills = discover_skills(tmp_path)

    assert "review" in skills
    assert skills["review"].completion_spec is None
    assert "UTF-8 JSON" in caplog.text


def test_invalid_hint_warns_without_disabling_valid_sidecar(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    skill_dir = _write_skill(
        tmp_path,
        argument_hint="x" * 1025,
        completion_path="completions.json",
    )
    spec = _valid_spec()
    _write_spec(skill_dir, spec)

    with caplog.at_level("WARNING"):
        metadata = discover_skills(tmp_path)["review"]

    assert metadata.argument_hint is None
    assert metadata.completion_spec == spec
    assert "argument-hint" in caplog.text


@pytest.mark.parametrize("argument_hint", [r"first\nsecond", r"red\x1b[31m"])
def test_non_printable_argument_hint_warns_without_disabling_valid_sidecar(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, argument_hint: str
):
    skill_dir = _write_skill(
        tmp_path,
        argument_hint=argument_hint,
        completion_path="completions.json",
    )
    spec = _valid_spec()
    _write_spec(skill_dir, spec)

    with caplog.at_level("WARNING"):
        metadata = discover_skills(tmp_path)["review"]

    assert metadata.argument_hint is None
    assert metadata.completion_spec == spec
    assert "printable single-line" in caplog.text


@pytest.mark.parametrize("completion_path", ["../outside.json", "/outside.json"])
def test_completion_sidecar_path_escape_is_rejected(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, completion_path: str
):
    skill_dir = _write_skill(tmp_path, completion_path=completion_path)
    _write_spec(tmp_path, _valid_spec(), "outside.json")

    with caplog.at_level("WARNING"):
        metadata = discover_skills(tmp_path)["review"]

    assert skill_dir.exists()
    assert metadata.completion_spec is None
    assert "metadata path must be relative" in caplog.text


def test_in_skill_completion_symlink_is_allowed(tmp_path: Path):
    skill_dir = _write_skill(tmp_path, completion_path="completions.json")
    targets_dir = skill_dir / "targets"
    targets_dir.mkdir()
    _write_spec(targets_dir, _valid_spec())
    os.symlink(targets_dir / "completions.json", skill_dir / "completions.json")

    assert discover_skills(tmp_path)["review"].completion_spec == _valid_spec()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFOs are unavailable on this platform")
def test_fifo_sidecar_is_rejected_without_attempting_to_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    skill_dir = _write_skill(tmp_path, completion_path="completions.json")
    os.mkfifo(skill_dir / "completions.json")

    def fail_if_read(*args, **kwargs):
        raise AssertionError("discovery must not read a FIFO sidecar")

    monkeypatch.setattr(discovery_module, "_read_completion_sidecar", fail_if_read)

    metadata = discover_skills(tmp_path)["review"]

    assert metadata.completion_spec is None


def test_completion_sidecar_symlink_loop_warns_without_dropping_skill(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    skill_dir = _write_skill(tmp_path, completion_path="completions.json")
    os.symlink("completions.json", skill_dir / "completions.json")

    with caplog.at_level("WARNING"):
        skills = discover_skills(tmp_path)

    assert "review" in skills
    assert skills["review"].completion_spec is None
    assert "Ignoring completions" in caplog.text


@pytest.mark.parametrize(
    "spec",
    [
        {
            "version": 1,
            "arguments": [{"after": [], "values": ["choice"]}] * 65,
        },
        {
            "version": 1,
            "arguments": [{"after": [f"token-{i}" for i in range(17)], "values": ["choice"]}],
        },
        {
            "version": 1,
            "arguments": [{"after": [], "values": [f"choice-{i}" for i in range(65)]}],
        },
        {
            "version": 1,
            "arguments": [{"after": [], "values": ["x" * 129]}],
        },
    ],
)
def test_completion_sidecar_caps_disable_only_completion_metadata(tmp_path: Path, spec: dict):
    skill_dir = _write_skill(tmp_path, completion_path="completions.json")
    _write_spec(skill_dir, spec)

    metadata = discover_skills(tmp_path)["review"]

    assert metadata.completion_spec is None


def test_completion_sidecar_byte_cap_disables_only_completion_metadata(tmp_path: Path):
    skill_dir = _write_skill(tmp_path, completion_path="completions.json")
    (skill_dir / "completions.json").write_bytes(b" " * (64 * 1024 + 1))

    metadata = discover_skills(tmp_path)["review"]

    assert metadata.completion_spec is None


def _metadata(
    name: str,
    *,
    shortcut: str | None = None,
    completion_spec: dict | None = None,
) -> SkillMetadata:
    return SkillMetadata(
        name=name,
        description=f"{name} description",
        path=Path(f"/unused/{name}/SKILL.md"),
        source="/unused",
        user_invocable=True,
        shortcut=shortcut,
        argument_hint="[target]",
        completion_spec=completion_spec,
    )


def test_completion_catalog_is_fresh_copy_and_performs_no_file_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    skill_dir = _write_skill(
        tmp_path, argument_hint="[target]", completion_path="completions.json"
    )
    _write_spec(skill_dir, _valid_spec())
    discovery = SkillsDiscovery(discover_skills(tmp_path))

    def fail_read_text(*args, **kwargs):
        raise AssertionError("completion catalog must not read from disk")

    monkeypatch.setattr(Path, "read_text", fail_read_text)
    catalog = discovery.get_completion_catalog()
    catalog[0]["arguments"][0]["values"].append("mutated")

    assert discovery.get_completion_catalog() == [
        {
            "name": "review",
            "aliases": [],
            "description": "Review a result",
            "argument_hint": "[target]",
            "arguments": _valid_spec()["arguments"],
        }
    ]


def test_completion_catalog_uses_the_existing_callable_alias_mapping():
    rules = _valid_spec()
    skills = {
        "review": _metadata("review", shortcut="rvw", completion_spec=rules),
    }
    discovery = SkillsDiscovery(skills)

    assert discovery.get_completion_catalog() == [
        {
            "name": "review",
            "aliases": ["rvw"],
            "description": "review description",
            "argument_hint": "[target]",
            "arguments": rules["arguments"],
        }
    ]
    assert discovery.get_shortcuts() == {
        "review": {
            "name": "review",
            "description": "review description",
            "context": None,
        },
        "rvw": {
            "name": "review",
            "description": "review description",
            "context": None,
        },
    }


def test_completion_catalog_omits_alias_lost_to_existing_shortcut_winner():
    skills = {
        "review": _metadata("review", shortcut="go", completion_spec=_valid_spec()),
        "go": _metadata("go", completion_spec=_valid_spec()),
    }

    catalog = SkillsDiscovery(skills).get_completion_catalog()

    assert next(record for record in catalog if record["name"] == "review")["aliases"] == []


def test_completion_catalog_observes_later_in_place_skill_merges():
    skills: dict[str, SkillMetadata] = {}
    discovery = SkillsDiscovery(skills)

    skills["review"] = _metadata("review", completion_spec=_valid_spec())

    assert [record["name"] for record in discovery.get_completion_catalog()] == ["review"]