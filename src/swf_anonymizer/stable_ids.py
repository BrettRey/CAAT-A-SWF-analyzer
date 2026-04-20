from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path

from .keymap import hash_alias, normalize_alias


EMPLOYEE_ID_PATTERN = re.compile(r"^N\d{8}$")


class StableFacultyIds:
    def __init__(
        self,
        path: Path,
        salt: str,
        alias_hashes: dict[str, str] | None = None,
    ) -> None:
        self.path = path
        self.salt = salt
        self.alias_hashes = alias_hashes or {}

    @classmethod
    def load(cls, path: Path) -> "StableFacultyIds":
        if not path.exists():
            return cls(path=path, salt=secrets.token_hex(16))

        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            path=path,
            salt=payload.get("salt") or secrets.token_hex(16),
            alias_hashes=payload.get("alias_hashes", {}),
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "salt": self.salt,
            "alias_hashes": dict(sorted(self.alias_hashes.items())),
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def resolve(self, aliases: list[str]) -> str | None:
        normalized_aliases = [normalize_alias(alias) for alias in aliases if normalize_alias(alias)]
        if not normalized_aliases:
            return None

        existing_ids: set[str] = set()
        for alias in normalized_aliases:
            alias_hash = self._lookup_alias_hash(alias)
            if alias_hash is not None:
                existing_ids.add(self.alias_hashes[alias_hash])

        if existing_ids:
            stable_id = sorted(existing_ids)[0]
        else:
            stable_id = make_stable_faculty_id(self.salt, choose_canonical_alias(normalized_aliases))

        for alias in normalized_aliases:
            self.alias_hashes[hash_alias(alias, self.salt)] = stable_id
        return stable_id

    def _lookup_alias_hash(self, alias: str) -> str | None:
        salted_hash = hash_alias(alias, self.salt)
        if salted_hash in self.alias_hashes:
            return salted_hash

        legacy_hash = hash_alias(alias)
        if legacy_hash in self.alias_hashes:
            self.alias_hashes[salted_hash] = self.alias_hashes[legacy_hash]
            return legacy_hash

        return None


def choose_canonical_alias(aliases: list[str]) -> str:
    employee_ids = sorted(alias for alias in aliases if EMPLOYEE_ID_PATTERN.match(alias))
    if employee_ids:
        return employee_ids[0]
    return sorted(aliases)[0]


def make_stable_faculty_id(salt: str, raw_alias: str) -> str:
    digest = hmac.new(
        salt.encode("utf-8"),
        normalize_alias(raw_alias).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"FID{digest[:12].upper()}"
