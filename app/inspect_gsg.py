from pathlib import Path
import re


GSG_FILES = [
    Path("data/sample_model/PERM_I.GSG"),
    Path("data/sample_model/PERM_J.GSG"),
    Path("data/sample_model/PERM_K.GSG"),
]


FLOAT_PATTERN = re.compile(
    r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?"
)


def looks_binary(raw: bytes) -> bool:
    if not raw:
        return False

    # If many null bytes or non-text bytes are present, likely binary.
    null_ratio = raw.count(b"\x00") / len(raw)
    non_text = sum(
        1 for b in raw
        if b not in b"\r\n\t" and (b < 32 or b > 126)
    )
    non_text_ratio = non_text / len(raw)

    return null_ratio > 0.01 or non_text_ratio > 0.10


def inspect_file(path: Path) -> None:
    print("")
    print("=" * 100)
    print(f"FILE: {path}")
    print("=" * 100)

    if not path.exists():
        print("MISSING")
        return

    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Size: {size_mb:.3f} MB")

    raw = path.read_bytes()
    sample = raw[:4096]

    is_binary = looks_binary(sample)
    print(f"Looks binary: {is_binary}")

    if is_binary:
        print("This file does not look like plain text. We may need a binary reader or a different export format.")
        print("First 64 bytes:")
        print(sample[:64])
        return

    text = raw.decode("utf-8", errors="ignore")

    lines = text.splitlines()
    print("")
    print("First 40 lines:")
    for i, line in enumerate(lines[:40], start=1):
        print(f"{i:03d}: {line[:220]}")

    numeric_tokens = FLOAT_PATTERN.findall(text)
    print("")
    print(f"Numeric tokens found: {len(numeric_tokens)}")

    if numeric_tokens:
        preview = numeric_tokens[:20]
        print("First numeric values:")
        print(preview)

        values = []
        for token in numeric_tokens[:100000]:
            try:
                values.append(float(token))
            except Exception:
                pass

        if values:
            print("")
            print("Stats on first numeric values:")
            print(f"count={len(values)}")
            print(f"min={min(values)}")
            print(f"max={max(values)}")
            print(f"first={values[0]}")
            print(f"last={values[-1]}")


def main() -> None:
    for path in GSG_FILES:
        inspect_file(path)


if __name__ == "__main__":
    main()
