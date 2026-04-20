from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path


TOKEN_PATTERN = re.compile(r"^(?P<prefix>[A-Z]+)(?P<number>\d+)$")


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class KeyMap:
    def __init__(
        self,
        path: Path,
        salt: str | None = None,
        alias_hashes: dict[str, str] | None = None,
        counters: dict[str, int] | None = None,
    ) -> None:
        self.path = path
        self.salt = salt or secrets.token_hex(16)
        # Raw aliases are kept in memory for the current process only.
        self.aliases: dict[str, str] = {}
        self.alias_hashes = alias_hashes or {}
        self.counters = counters or {}
        self._sync_counters_with_aliases()

    @classmethod
    def load(cls, path: Path) -> "KeyMap":
        if not path.exists():
            return cls(path=path, salt=secrets.token_hex(16))

        payload = json.loads(path.read_text(encoding="utf-8"))
        alias_hashes = payload.get("alias_hashes")
        if alias_hashes is None:
            alias_hashes = {
                hash_alias(alias, payload.get("salt") or ""): token
                for alias, token in payload.get("aliases", {}).items()
            }

        return cls(
            path=path,
            salt=payload.get("salt") or secrets.token_hex(16),
            alias_hashes=alias_hashes,
            counters=payload.get("counters", {}),
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "salt": self.salt,
            "alias_hashes": dict(sorted(self.alias_hashes.items())),
            "counters": dict(sorted(self.counters.items())),
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def ensure_alias(self, raw_value: str, prefix: str) -> str:
        alias = normalize_alias(raw_value)
        if not alias:
            raise ValueError("Cannot assign a token to an empty alias.")

        existing = self._lookup_token(alias)
        if existing:
            self.aliases[alias] = existing
            return existing

        token = self._allocate_token(prefix)
        self.aliases[alias] = token
        self.alias_hashes[hash_alias(alias, self.salt)] = token
        return token

    def link_alias(self, raw_value: str, token: str) -> str:
        alias = normalize_alias(raw_value)
        if not alias:
            raise ValueError("Cannot link an empty alias.")

        self.aliases[alias] = token
        self.alias_hashes[hash_alias(alias, self.salt)] = token
        self._sync_counter_from_token(token)
        return token

    def aliases_present_in(self, text: str) -> dict[str, str]:
        matches: dict[str, str] = {}
        for alias, token in self.aliases.items():
            if alias and alias in text:
                matches[alias] = token
        return matches

    def _allocate_token(self, prefix: str) -> str:
        next_number = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = next_number
        return f"{prefix}{next_number:03d}"

    def _lookup_token(self, alias: str) -> str | None:
        salted_hash = hash_alias(alias, self.salt)
        if salted_hash in self.alias_hashes:
            return self.alias_hashes[salted_hash]

        legacy_hash = hash_alias(alias)
        existing = self.alias_hashes.get(legacy_hash)
        if existing:
            self.alias_hashes[salted_hash] = existing
            return existing

        return None

    def _sync_counters_with_aliases(self) -> None:
        for token in self.alias_hashes.values():
            self._sync_counter_from_token(token)

    def _sync_counter_from_token(self, token: str) -> None:
        match = TOKEN_PATTERN.match(token)
        if not match:
            return

        prefix = match.group("prefix")
        number = int(match.group("number"))
        self.counters[prefix] = max(number, self.counters.get(prefix, 0))


def hash_alias(value: str, salt: str = "") -> str:
    normalized = normalize_alias(value).encode("utf-8")
    if salt:
        return hmac.new(salt.encode("utf-8"), normalized, hashlib.sha256).hexdigest()
    return hashlib.sha256(normalized).hexdigest()
