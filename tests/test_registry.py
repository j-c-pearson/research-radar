from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from litreview.registry import RegistryValidationError, load_registry


def test_registry_loads() -> None:
    registry = load_registry(Path("registry.yaml"))

    assert registry.version == 1
    assert {source.id for source in registry.sources} == {"openalex", "europe_pmc", "biorxiv", "medrxiv", "arxiv"}
    assert any(item.name == "Cristina Stoica" and item.orcid == "0000-0002-5838-599X" for item in registry.watchlist)


def test_duplicate_topic_ids_fail(tmp_path: Path) -> None:
    data = yaml.safe_load(Path("registry.yaml").read_text())
    data["topics"][1]["id"] = data["topics"][0]["id"]
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(RegistryValidationError, match="Duplicate topic ID"):
        load_registry(path)


def test_bad_orcid_fails(tmp_path: Path) -> None:
    data = yaml.safe_load(Path("registry.yaml").read_text())
    data["watchlist"][0]["orcid"] = "bad"
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(RegistryValidationError, match="malformed ORCID"):
        load_registry(path)


def test_unknown_topic_reference_fails(tmp_path: Path) -> None:
    data = yaml.safe_load(Path("registry.yaml").read_text())
    data["watchlist"][0]["related_topics"] = ["missing_topic"]
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(RegistryValidationError, match="unknown topic"):
        load_registry(path)

