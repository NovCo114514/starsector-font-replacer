from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import shutil

from .errors import FontGenError


PACK_WARNING = "this is a core-overwrite font pack"


@dataclass(frozen=True)
class BuildPackConfig:
    replacement_font_dir: Path
    report: Path
    output_pack: Path
    pack_name: str
    force: bool = False


@dataclass(frozen=True)
class BuildPackResult:
    output_pack: Path
    replacement_files: list[Path]
    manifest_path: Path
    install_script: Path
    uninstall_script: Path
    readme_path: Path
    copied_report: Path


def build_pack(config: BuildPackConfig) -> BuildPackResult:
    validate_config(config)
    if config.output_pack.exists():
        if not config.force:
            raise FontGenError(
                f"Output pack already exists: {config.output_pack}. Pass --force to overwrite."
            )
        remove_existing_pack(config.output_pack, config.replacement_font_dir)

    pack_root = config.output_pack
    replacement_target = pack_root / "replacement_fonts"
    pack_root.mkdir(parents=True, exist_ok=False)
    replacement_target.mkdir()

    replacement_files = copy_replacement_fonts(config.replacement_font_dir, replacement_target)
    copied_report = pack_root / "rebuild_fontlib_report.md"
    shutil.copy2(config.report, copied_report)

    manifest_path = pack_root / "manifest.json"
    install_script = pack_root / "install_font_pack.ps1"
    uninstall_script = pack_root / "uninstall_font_pack.ps1"
    readme_path = pack_root / "README.md"

    manifest_path.write_text(
        json.dumps(
            build_manifest(config, replacement_files),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    install_script.write_text(build_install_script(config.pack_name), encoding="utf-8")
    uninstall_script.write_text(build_uninstall_script(), encoding="utf-8")
    readme_path.write_text(build_pack_readme(config.pack_name), encoding="utf-8")

    return BuildPackResult(
        output_pack=pack_root,
        replacement_files=replacement_files,
        manifest_path=manifest_path,
        install_script=install_script,
        uninstall_script=uninstall_script,
        readme_path=readme_path,
        copied_report=copied_report,
    )


def validate_config(config: BuildPackConfig) -> None:
    if not config.pack_name.strip():
        raise FontGenError("--pack-name must not be empty")
    if not config.replacement_font_dir.exists():
        raise FontGenError(f"--replacement-font-dir does not exist: {config.replacement_font_dir}")
    if not config.replacement_font_dir.is_dir():
        raise FontGenError(f"--replacement-font-dir must be a directory: {config.replacement_font_dir}")
    if not config.report.exists():
        raise FontGenError(f"--report does not exist: {config.report}")
    if not config.report.is_file():
        raise FontGenError(f"--report must be a file: {config.report}")
    if config.output_pack.exists() and not config.output_pack.is_dir():
        raise FontGenError(f"--output-pack exists and is not a directory: {config.output_pack}")
    try:
        replacement = config.replacement_font_dir.resolve()
        output = config.output_pack.resolve()
    except OSError:
        return
    if output == replacement:
        raise FontGenError("--output-pack must be different from --replacement-font-dir")
    if output in replacement.parents:
        raise FontGenError("--output-pack must not be inside --replacement-font-dir")


def remove_existing_pack(output_pack: Path, replacement_font_dir: Path) -> None:
    output = output_pack.resolve()
    replacement = replacement_font_dir.resolve()
    if output.parent == output or output == replacement or output in replacement.parents:
        raise FontGenError(f"Refusing to remove unsafe output pack path: {output_pack}")
    shutil.rmtree(output_pack)


def copy_replacement_fonts(source_dir: Path, target_dir: Path) -> list[Path]:
    copied: list[Path] = []
    for source in sorted(source_dir.rglob("*"), key=lambda path: str(path).lower()):
        if not source.is_file() or source.suffix.lower() not in {".fnt", ".png"}:
            continue
        relative = source.relative_to(source_dir)
        target = target_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(Path("replacement_fonts") / relative)
    if not copied:
        raise FontGenError(f"No .fnt or .png files found in replacement font dir: {source_dir}")
    return copied


def build_manifest(config: BuildPackConfig, replacement_files: list[Path]) -> dict[str, object]:
    return {
        "pack_name": config.pack_name,
        "build_time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "replacement_font_files": [path.as_posix() for path in replacement_files],
        "source_report_path": str(config.report),
        "file_count": len(replacement_files),
        "warning": PACK_WARNING,
    }


def build_install_script(pack_name: str) -> str:
    escaped_pack_name = pack_name.replace("'", "''")
    return f"""$ErrorActionPreference = "Stop"

$PackName = '{escaped_pack_name}'
$PackRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReplacementDir = Join-Path $PackRoot "replacement_fonts"
$PackageManifestPath = Join-Path $PackRoot "manifest.json"
$InstallManifestPath = Join-Path $PackRoot "install_manifest.json"

Write-Host "Installing $PackName"
Write-Host "This is a core-overwrite font pack. Use a copied Starsector test install first."

$StarsectorRoot = Read-Host "Enter Starsector root directory"
if ([string]::IsNullOrWhiteSpace($StarsectorRoot)) {{
  throw "Starsector root directory is required."
}}
$StarsectorRoot = $StarsectorRoot.Trim('"')

if (!(Test-Path -LiteralPath $StarsectorRoot -PathType Container)) {{
  throw "Starsector root directory does not exist: $StarsectorRoot"
}}

$FontsDir = Join-Path $StarsectorRoot "starsector-core\\graphics\\fonts"
if (!(Test-Path -LiteralPath $FontsDir -PathType Container)) {{
  throw "Could not find starsector-core\\graphics\\fonts under: $StarsectorRoot"
}}

if (!(Test-Path -LiteralPath $ReplacementDir -PathType Container)) {{
  throw "Missing replacement_fonts directory next to this installer: $ReplacementDir"
}}

$BackupRoot = Join-Path $StarsectorRoot "backups"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $BackupRoot "fonts_backup_$Timestamp"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

Get-ChildItem -LiteralPath $FontsDir -Force | Copy-Item -Destination $BackupDir -Recurse -Force

$InstalledFiles = @()
Get-ChildItem -LiteralPath $ReplacementDir -Recurse -File |
  Where-Object {{ $_.Extension -in @(".fnt", ".png") }} |
  ForEach-Object {{
    $Relative = $_.FullName.Substring($ReplacementDir.Length).TrimStart("\\", "/")
    $Destination = Join-Path $FontsDir $Relative
    $DestinationParent = Split-Path -Parent $Destination
    if (!(Test-Path -LiteralPath $DestinationParent -PathType Container)) {{
      New-Item -ItemType Directory -Path $DestinationParent -Force | Out-Null
    }}
    Copy-Item -LiteralPath $_.FullName -Destination $Destination -Force
    $InstalledFiles += $Relative
  }}

$InstallManifest = [ordered]@{{
  pack_name = $PackName
  installed_at = (Get-Date).ToString("o")
  starsector_root = $StarsectorRoot
  fonts_dir = $FontsDir
  backup_dir = $BackupDir
  package_manifest = $PackageManifestPath
  installed_files = $InstalledFiles
}}

$InstallManifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $InstallManifestPath -Encoding UTF8

Write-Host "Install complete."
Write-Host "Backup path: $BackupDir"
Write-Host "Install manifest: $InstallManifestPath"
"""


def build_uninstall_script() -> str:
    return """$ErrorActionPreference = "Stop"

$PackRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallManifestPath = Join-Path $PackRoot "install_manifest.json"

if (!(Test-Path -LiteralPath $InstallManifestPath -PathType Leaf)) {
  throw "Missing install_manifest.json next to this uninstaller. Run install_font_pack.ps1 first."
}

$InstallManifest = Get-Content -LiteralPath $InstallManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$FontsDir = [string]$InstallManifest.fonts_dir
$BackupDir = [string]$InstallManifest.backup_dir

if (!(Test-Path -LiteralPath $BackupDir -PathType Container)) {
  throw "Backup directory does not exist: $BackupDir"
}

$FontsParent = Split-Path -Parent $FontsDir
if (!(Test-Path -LiteralPath $FontsParent -PathType Container)) {
  New-Item -ItemType Directory -Path $FontsParent -Force | Out-Null
}

if (Test-Path -LiteralPath $FontsDir -PathType Container) {
  Remove-Item -LiteralPath $FontsDir -Recurse -Force
}
New-Item -ItemType Directory -Path $FontsDir -Force | Out-Null
Get-ChildItem -LiteralPath $BackupDir -Force | Copy-Item -Destination $FontsDir -Recurse -Force

Write-Host "Fonts restored from backup."
Write-Host "Restored fonts directory: $FontsDir"
Write-Host "Backup used: $BackupDir"
"""


def build_pack_readme(pack_name: str) -> str:
    return f"""# {pack_name}

This is not a regular Starsector mod. It is a core-overwrite font replacement pack.

## Safety First

Strongly recommended workflow:

1. Make a full copy of your Starsector install for testing.
2. Run this pack only against that copied test install first.
3. Do not overwrite your only Starsector game directory.
4. Keep the generated backup until you have tested the game.

The installer does not require administrator permissions. It only writes inside the Starsector directory you enter.

## Install

Open PowerShell in this pack directory and run:

```powershell
.\\install_font_pack.ps1
```

When prompted, enter the Starsector root directory. The script checks for:

```text
starsector-core/graphics/fonts
```

It then creates a timestamped backup under:

```text
backups/fonts_backup_YYYYMMDD_HHMMSS
```

Only `.fnt` and `.png` files from `replacement_fonts/` are copied into the game fonts folder. Markdown and JSON files are not copied there.

## Uninstall / Roll Back

Run:

```powershell
.\\uninstall_font_pack.ps1
```

The uninstaller reads `install_manifest.json`, finds the backup directory, and restores the previous `starsector-core/graphics/fonts` folder.

## Missing Character Risk

This pack may have been built from a filtered charset. Filtering lets a target font generate successfully, but any character removed during filtering can still appear as missing text in-game. Review the charset filter report and test in a copied Starsector install.

## Included Files

- `replacement_fonts/`: generated `.fnt` and `.png` files
- `rebuild_fontlib_report.md`: generation report
- `manifest.json`: pack metadata
- `install_font_pack.ps1`: installer
- `uninstall_font_pack.ps1`: rollback script
"""
