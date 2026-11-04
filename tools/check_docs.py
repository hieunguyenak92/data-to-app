"""Check release documentation links, language selectors and shared commands."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
READMES = ["README.md", "README.vi.md", "README.ko.md", "README.ja.md", "README.es.md",
           "README.pt-BR.md", "README.zh-CN.md", "README.th.md", "README.fr.md"]


def main():
    errors = []
    reference_commands = None
    for name in READMES:
        path = ROOT / name
        if not path.is_file():
            errors.append(f"Missing {name}")
            continue
        text = path.read_text(encoding="utf-8")
        for target in READMES:
            if f"]({target})" not in text:
                errors.append(f"{name}: missing selector {target}")
        commands = re.findall(r"```bash\n(.*?)```", text, re.S)
        if reference_commands is None:
            reference_commands = commands
        elif commands != reference_commands:
            errors.append(f"{name}: shared bash commands differ")
        if "docs/assets/workspace.jpg" not in text:
            errors.append(f"{name}: missing verified screenshot")
    for path in ROOT.rglob("*.md"):
        if any(part in {".git", ".venv", "dist", "inventory-app"} for part in path.relative_to(ROOT).parts):
            continue
        for target in re.findall(r"\]\(([^\s)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith(("#", "mailto:")) or "<" in target:
                continue
            local = (path.parent / target.split("#", 1)[0]).resolve()
            if not local.exists():
                errors.append(f"{path.relative_to(ROOT)}: missing {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print("Documentation links, nine selectors, screenshots and shared commands pass.")


if __name__ == "__main__":
    main()
