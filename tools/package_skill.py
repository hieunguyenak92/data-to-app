"""Build a reproducible installable skill ZIP without generated/private state."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "skills" / "data-to-app"
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    output = destination / "data-to-app-0.1.0.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or any(part == "__pycache__" for part in path.parts) or path.suffix == ".pyc":
                continue
            if path.is_symlink():
                raise SystemExit(f"Refusing symlink in skill: {path}")
            relative = Path("data-to-app") / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), (2026, 11, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    print(output)


if __name__ == "__main__":
    main()
