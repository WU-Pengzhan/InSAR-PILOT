"""Authenticated, metadata-only selection of paths on the processing host.

Browsers cannot expose absolute local paths through an HTML upload picker.
Directory navigation uses signed resource IDs; no file contents are served here.
"""

from __future__ import annotations

import base64
import hashlib
import heapq
import hmac
import os
import re
import secrets
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


def wsl_distribution() -> str | None:
    return os.environ.get("WSL_DISTRO_NAME") or None


def host_path(value: str) -> Path:
    """Translate explicit Windows paths only on WSL; preserve executable symlinks."""
    if not value or "\x00" in value:
        raise ValueError("Choose an absolute path on the processing host.")
    windows = value.replace("\\", "/")
    distro = wsl_distribution()
    if windows.startswith("//"):
        parts = windows.split("/")
        if len(parts) < 4 or parts[2].lower() not in {"wsl$", "wsl.localhost"}:
            raise ValueError("Network paths must first be mounted in Linux.")
        if not distro or parts[3].casefold() != distro.casefold():
            raise ValueError("Choose a path in the WSL distribution running InSAR-PILOT.")
        value = "/" + "/".join(parts[4:])
    elif re.match(r"^[A-Za-z]:", value):
        if not distro or not re.match(r"^[A-Za-z]:[/\\]", value):
            raise ValueError("Windows drive paths require WSL and an absolute path, for example C:\\Data.")
        try:
            translated = subprocess.run(["wslpath", "-u", value], capture_output=True, text=True, timeout=5, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("Windows path could not be mapped. Choose its mounted Linux location.") from exc
        value = translated.stdout.rstrip("\r\n")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("Choose an absolute Linux path or a mounted Windows drive in WSL.")
    # Do not resolve bin/python symlinks: the venv location determines the runtime.
    return path


class FileEntry(BaseModel):
    resource_id: str
    name: str
    path: str
    kind: Literal["directory", "file"]


class FileLocations(BaseModel):
    environment: Literal["linux", "wsl"]
    distribution: str | None
    locations: list[FileEntry]


class DirectoryPage(BaseModel):
    directory: FileEntry
    parent_id: str | None
    breadcrumbs: list[FileEntry]
    entries: list[FileEntry]
    next_offset: int | None


class ResolvePath(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class ResolvedPath(BaseModel):
    entry: FileEntry
    directory_id: str


class FileBrowser:
    def __init__(self, library: Path) -> None:
        self.library = library
        self.key = secrets.token_bytes(32)

    def resource_id(self, path: Path) -> str:
        payload = base64.urlsafe_b64encode(os.fsencode(path)).decode("ascii")
        signature = hmac.new(self.key, payload.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def path(self, resource_id: str) -> Path:
        try:
            payload, signature = resource_id.rsplit(".", 1)
            expected = hmac.new(self.key, payload.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            path = Path(os.fsdecode(base64.b64decode(payload, altchars=b"-_", validate=True)))
            if not path.is_absolute():
                raise ValueError
            return path
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Selection expired or invalid. Reopen the file browser.") from exc

    def entry(self, path: Path) -> FileEntry:
        if not path.is_dir() and not path.is_file():
            raise FileNotFoundError(f"File or directory is unavailable: {path}")
        return FileEntry(
            resource_id=self.resource_id(path),
            name=path.name or "/",
            path=str(path),
            kind="directory" if path.is_dir() else "file",
        )

    def locations(self) -> FileLocations:
        distro = wsl_distribution()
        paths = [Path.home(), self.library, Path("/")]
        # Local removable disks on Linux; Windows disks and other mounts on WSL.
        for mount in (Path("/mnt"), Path("/media") / Path.home().name, Path("/run/media") / Path.home().name):
            if mount.is_dir():
                paths.append(mount)
                with suppress(OSError):
                    paths.extend(sorted(p for p in mount.iterdir() if p.is_mount()))
        entries = []
        for path in dict.fromkeys(paths):
            try:
                entries.append(self.entry(path))
            except OSError:
                continue
        return FileLocations(environment="wsl" if distro else "linux", distribution=distro, locations=entries)

    def resolve(self, value: str) -> ResolvedPath:
        path = host_path(value)
        entry = self.entry(path)
        return ResolvedPath(entry=entry, directory_id=self.resource_id(path if path.is_dir() else path.parent))

    def browse(
        self,
        resource_id: str,
        *,
        offset: int,
        limit: int,
        search: str,
        hidden: bool,
        directories_only: bool,
        extension: str = "",
    ) -> DirectoryPage:
        directory = self.path(resource_id)
        if not directory.is_dir():
            raise NotADirectoryError(str(directory))
        needle = search.casefold()
        # Bound response and selection memory; never recurse into SAFE directories.
        with os.scandir(directory) as children:

            def candidates():
                for child in children:
                    if (not hidden and child.name.startswith(".")) or needle not in child.name.casefold():
                        continue
                    try:
                        is_dir = child.is_dir()
                        if is_dir or (
                            not directories_only
                            and child.is_file()
                            and (not extension or child.name.lower().endswith(extension.lower()))
                        ):
                            yield (not is_dir, child.name.casefold(), child.name)
                    except OSError:
                        continue

            names = heapq.nsmallest(offset + limit + 1, candidates())
        entries = []
        for _, _, name in names[offset : offset + limit]:
            try:
                entries.append(self.entry(directory / name))
            except OSError:
                continue  # A concurrently removed item is no longer selectable.
        return DirectoryPage(
            directory=self.entry(directory),
            parent_id=self.resource_id(directory.parent) if directory.parent != directory else None,
            breadcrumbs=[self.entry(p) for p in reversed(directory.parents)] + [self.entry(directory)],
            entries=entries,
            next_offset=offset + limit if len(names) > offset + limit else None,
        )
