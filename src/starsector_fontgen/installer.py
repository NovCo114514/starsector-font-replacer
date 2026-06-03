from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import shutil

from .errors import FontGenError


@dataclass(frozen=True)
class InstallConfig:
    starsector_root: Path
    replacement_font_dir: Path
    manifest_path: Path
    pack_name: str = "Starsector Font Replacer"


@dataclass(frozen=True)
class InstallResult:
    fonts_dir: Path
    backup_dir: Path
    manifest_path: Path
    installed_files: list[str]


@dataclass(frozen=True)
class RestoreResult:
    fonts_dir: Path
    backup_dir: Path


def starsector_fonts_dir(starsector_root: Path) -> Path:
    return starsector_root / "starsector-core" / "graphics" / "fonts"


def validate_starsector_root(starsector_root: Path) -> Path:
    if not starsector_root.exists():
        raise FontGenError(f"Starsector root does not exist: {starsector_root}")
    if not starsector_root.is_dir():
        raise FontGenError(f"Starsector root must be a directory: {starsector_root}")
    fonts_dir = starsector_fonts_dir(starsector_root)
    if not fonts_dir.exists() or not fonts_dir.is_dir():
        raise FontGenError(f"Could not find starsector-core\\graphics\\fonts under: {starsector_root}")
    return fonts_dir


def install_replacement_fonts(config: InstallConfig) -> InstallResult:
    fonts_dir = validate_starsector_root(config.starsector_root)
    if not config.replacement_font_dir.exists() or not config.replacement_font_dir.is_dir():
        raise FontGenError(f"Replacement font dir does not exist: {config.replacement_font_dir}")

    replacement_files = iter_replacement_files(config.replacement_font_dir)
    if not replacement_files:
        raise FontGenError(f"No .fnt or .png files found in: {config.replacement_font_dir}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = config.starsector_root / "backups" / f"fonts_backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    copy_dir_contents(fonts_dir, backup_dir)

    installed_files: list[str] = []
    for source in replacement_files:
        relative = source.relative_to(config.replacement_font_dir)
        destination = fonts_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        installed_files.append(relative.as_posix())

    config.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "pack_name": config.pack_name,
        "installed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "starsector_root": str(config.starsector_root),
        "fonts_dir": str(fonts_dir),
        "backup_dir": str(backup_dir),
        "replacement_font_dir": str(config.replacement_font_dir),
        "installed_files": installed_files,
    }
    config.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return InstallResult(
        fonts_dir=fonts_dir,
        backup_dir=backup_dir,
        manifest_path=config.manifest_path,
        installed_files=installed_files,
    )


def restore_from_manifest(manifest_path: Path) -> RestoreResult:
    if not manifest_path.exists() or not manifest_path.is_file():
        raise FontGenError(f"install_manifest.json does not exist: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FontGenError(f"Could not parse install manifest: {manifest_path}") from exc

    fonts_dir = Path(str(manifest.get("fonts_dir", "")))
    backup_dir = Path(str(manifest.get("backup_dir", "")))
    if not backup_dir.exists() or not backup_dir.is_dir():
        raise FontGenError(f"Backup directory does not exist: {backup_dir}")

    fonts_dir.parent.mkdir(parents=True, exist_ok=True)
    if fonts_dir.exists():
        shutil.rmtree(fonts_dir)
    fonts_dir.mkdir(parents=True)
    copy_dir_contents(backup_dir, fonts_dir)
    return RestoreResult(fonts_dir=fonts_dir, backup_dir=backup_dir)


def iter_replacement_files(replacement_font_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in replacement_font_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in {".fnt", ".png"}
        ),
        key=lambda path: str(path.relative_to(replacement_font_dir)).lower(),
    )


def copy_dir_contents(source_dir: Path, destination_dir: Path) -> None:
    for source in source_dir.rglob("*"):
        relative = source.relative_to(source_dir)
        destination = destination_dir / relative
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
