"""
Skill Loader – fetches and caches SKILL.md from external sources.

Supported source types:
    github    – raw.githubusercontent.com (public) or GitHub API (private)
    skillstore – skillstore.io REST API
    local     – local filesystem path (dev/testing)
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict

import frontmatter
import httpx
import yaml

from app.config import settings

log = logging.getLogger("skill-runner.loader")

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: Dict[str, Dict[str, Any]] = {}


def load_registry() -> Dict[str, Dict[str, Any]]:
    """Parse skills/registry.yaml and return the skills dict."""
    path = Path(settings.skills_registry_path)
    if not path.exists():
        log.warning("Skills registry not found at %s", path)
        return {}
    with path.open() as f:
        data = yaml.safe_load(f)
    return data.get("skills", {})


def get_registry() -> Dict[str, Dict[str, Any]]:
    """Return (and lazy-init) the global registry."""
    global _registry
    if not _registry:
        _registry = load_registry()
    return _registry


# ---------------------------------------------------------------------------
# SKILL.md cache
# ---------------------------------------------------------------------------

_skill_cache: Dict[str, str] = {}   # skill_id → SKILL.md content
_skill_meta: Dict[str, Dict[str, Any]] = {}  # skill_id → parsed frontmatter metadata


def _cache_path(skill_id: str) -> Path:
    cache_dir = Path(settings.skill_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_id = skill_id.replace("/", "_")
    return cache_dir / f"{safe_id}.SKILL.md"


async def _fetch_github(skill_id: str, source: Dict[str, Any]) -> str:
    repo = source["repo"]
    ref = source.get("ref", "main")
    skill_file = source.get("skill_file", "SKILL.md")
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{skill_file}"

    headers: Dict[str, str] = {}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"

    log.info("Fetching SKILL.md for %s from %s", skill_id, url)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


async def _fetch_skillstore(skill_id: str, source: Dict[str, Any]) -> str:
    """Fetch SKILL.md from skillstore.io."""
    slug = source.get("skill_id", skill_id)
    version = source.get("version", "latest")
    url = f"https://skillstore.io/api/v1/skills/{slug}/skill.md?version={version}"

    log.info("Fetching SKILL.md for %s from skillstore.io", skill_id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def _fetch_local(skill_id: str, source: Dict[str, Any]) -> str:
    path = Path(source["path"])
    if not path.exists():
        raise FileNotFoundError(f"Local skill file not found: {path}")
    return path.read_text()


async def fetch_skill(skill_id: str) -> str:
    """
    Fetch the SKILL.md for a skill_id.
    Returns cached version if available, else fetches from source.
    """
    if skill_id in _skill_cache:
        return _skill_cache[skill_id]

    cache_file = _cache_path(skill_id)
    if cache_file.exists():
        content = cache_file.read_text()
        _skill_cache[skill_id] = content
        log.debug("Skill %s loaded from disk cache", skill_id)
        return content

    registry = get_registry()
    if skill_id not in registry:
        raise ValueError(f"Skill '{skill_id}' not found in registry")

    source = registry[skill_id].get("source", {})
    source_type = source.get("type", "github")

    if source_type == "github":
        content = await _fetch_github(skill_id, source)
    elif source_type == "skillstore":
        content = await _fetch_skillstore(skill_id, source)
    elif source_type == "local":
        content = _fetch_local(skill_id, source)
    else:
        raise ValueError(f"Unknown skill source type: {source_type}")

    # Persist to disk cache
    cache_file.write_text(content)
    _skill_cache[skill_id] = content
    log.info("Skill %s fetched and cached", skill_id)
    return content


def get_skill_metadata(skill_id: str) -> Dict[str, Any]:
    """Parse the SKILL.md frontmatter for a cached skill."""
    if skill_id in _skill_meta:
        return _skill_meta[skill_id]

    content = _skill_cache.get(skill_id, "")
    if not content:
        return {}

    try:
        post = frontmatter.loads(content)
        meta = dict(post.metadata)
        _skill_meta[skill_id] = meta
        return meta
    except Exception as exc:
        log.warning("Could not parse frontmatter for skill %s: %s", skill_id, exc)
        return {}


def get_skill_mcp_server(skill_id: str) -> str | None:
    """Return the MCP server URL for a skill (from registry, falling back to frontmatter)."""
    registry = get_registry()
    if skill_id in registry:
        mcp = registry[skill_id].get("mcp_server")
        if mcp:
            return mcp
    meta = get_skill_metadata(skill_id)
    return meta.get("metadata", {}).get("mcp_server")


def get_skill_auth_token(skill_id: str) -> str:
    """
    Return the auth token for a skill's MCP server.
    Token env var name = skill_id uppercased with hyphens→underscores + _MCP_TOKEN
    e.g. raindrop-io → RAINDROP_IO_MCP_TOKEN
    """
    env_key = skill_id.upper().replace("-", "_") + "_MCP_TOKEN"
    return os.environ.get(env_key, "")


async def prefetch_all() -> None:
    """Warm the cache for all skills in the registry at startup."""
    registry = get_registry()
    for skill_id in registry:
        try:
            await fetch_skill(skill_id)
            log.info("Pre-fetched skill: %s", skill_id)
        except Exception as exc:
            log.error("Failed to pre-fetch skill %s: %s", skill_id, exc)
