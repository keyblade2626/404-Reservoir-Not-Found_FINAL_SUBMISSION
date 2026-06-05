import re
from pathlib import Path

ROOT = Path(".")

allowed_ext = {
    ".py", ".md", ".json", ".txt", ".example", ".env", ".yml", ".yaml", ".toml", ".sh", ".ps1"
}

secret_patterns = [
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("Google-style key", re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")),
    ("GitHub PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b")),
    ("RSA private key block", re.compile(r"-----BEGIN RSA PRIVATE KEY-----")),
    ("OpenSSH private key block", re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----")),
    ("Generic private key block", re.compile(r"-----BEGIN PRIVATE KEY-----")),
]

env_key_pattern = re.compile(
    r"^\s*(OPENAI_API_KEY|COMPASS_API_KEY|AZURE_OPENAI_API_KEY)\s*=\s*(.+?)\s*$",
    re.IGNORECASE,
)

allowed_placeholder_values = {
    "",
    "your-compass-api-key-here",
    "your-api-key-here",
    "placeholder",
    "<your-compass-api-key>",
    "<your-api-key>",
}

excluded_dirs = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}

excluded_files = {
    "improved_secret_scan.py",  # avoid matching the scanner's own regex strings
}

hits = []

for p in ROOT.rglob("*"):
    if not p.is_file():
        continue

    parts = set(p.parts)

    if parts.intersection(excluded_dirs):
        continue

    if p.name in excluded_files:
        continue

    if p.name == ".env":
        continue

    if p.suffix.lower() not in allowed_ext:
        continue

    try:
        lines = p.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    except Exception:
        continue

    for i, line in enumerate(lines, start=1):
        for label, pattern in secret_patterns:
            if pattern.search(line):
                hits.append((str(p), i, label, line.strip()))

        m = env_key_pattern.match(line)
        if m:
            value = m.group(2).strip().strip('"').strip("'")
            if value not in allowed_placeholder_values:
                hits.append((str(p), i, "Non-placeholder API key assignment", line.strip()))

if hits:
    print("Potential secret hits found:")
    for path, line_no, label, line in hits:
        print(f"{path}:{line_no}: {label}: {line}")
    raise SystemExit(1)

print("[OK] No obvious secrets found outside local .env")
