"""Private, immutable CSP revisions shared by local Claude MCP connections."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from leadgenerator.kernel.composition import private_home
from leadgenerator.research.url_safety import validate_public_url


class ImagePolicyStore:
    """Persist exact public origins, never assets, lead records or credentials.

    One immutable file per origin avoids lost updates between the model's MCP
    process and Desktop's independent widget connection. Content-addressed policies
    let a host cache resources without reusing an obsolete image allowlist.
    """

    def __init__(self, home: Path | None = None):
        self.root = (home or private_home()) / "ui-image-policies"

    @staticmethod
    def _directory(path: Path) -> None:
        if path.is_symlink():
            raise ValueError("Le dossier des autorisations d’images est invalide.")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _write(self, path: Path, text: str) -> None:
        self._directory(self.root)
        self._directory(path.parent)
        fd, temporary = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _digest(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    @staticmethod
    def _validate_origin(origin: str, *, resolve: bool = True) -> None:
        if not isinstance(origin, str) or len(origin) > 2048:
            raise ValueError("Le domaine d’image est invalide.")
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or "*" in parsed.netloc
            or origin != f"https://{parsed.netloc.lower()}"
        ):
            raise ValueError("Le domaine d’image est invalide.")
        if resolve:
            validate_public_url(origin)

    def record(self, origins: set[str]) -> None:
        for origin in origins:
            self._validate_origin(origin)
            self._write(self.root / "origins" / self._digest(origin), origin)

    def current(self) -> str | None:
        folder = self.root / "origins"
        if self.root.is_symlink() or folder.is_symlink():
            raise ValueError("Le dossier des autorisations d’images est invalide.")
        if not folder.exists():
            return None
        origins = []
        for path in sorted(folder.iterdir()):
            if not re.fullmatch(r"[a-f0-9]{64}", path.name) or path.is_symlink():
                continue
            if not path.is_file() or path.stat().st_size > 2048:
                raise ValueError("Une autorisation d’image est invalide.")
            value = path.read_text(encoding="utf-8")
            if len(value) > 2048 or self._digest(value) != path.name:
                raise ValueError("Une autorisation d’image est invalide.")
            # Tool discovery must not resolve every historical image hostname.
            # Resolve when recording and when actually reading the UI policy.
            self._validate_origin(value, resolve=False)
            origins.append(value)
            if len(origins) > 1024:
                raise ValueError("Le catalogue de domaines d’images doit être révisé.")
        if not origins:
            return None
        text = json.dumps(sorted(set(origins)), separators=(",", ":"))
        digest = self._digest(text)
        path = self.root / "policies" / digest
        if not path.is_file() or path.is_symlink():
            self._write(path, text)
        return digest

    def read(self, digest: str) -> set[str]:
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("La révision des images est invalide.")
        path = self.root / "policies" / digest
        if self.root.is_symlink() or path.parent.is_symlink() or path.is_symlink():
            raise ValueError("La révision des images est invalide.")
        if not path.is_file() or path.stat().st_size > 2_100_000:
            raise ValueError("La révision des images est invalide.")
        text = path.read_text(encoding="utf-8")
        if len(text) > 2_100_000 or self._digest(text) != digest:
            raise ValueError("La révision des images est invalide.")
        origins = json.loads(text)
        if not isinstance(origins, list) or len(origins) > 1024:
            raise ValueError("La révision des images est invalide.")
        for origin in origins:
            self._validate_origin(origin)
        return set(origins)
