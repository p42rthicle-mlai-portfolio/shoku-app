from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_OUTPUT = ROOT_DIR / "backup_data.zip"
BACKUP_FILES = [
    "foods.csv",
    "dishes.csv",
    "dish_ingredients.csv",
    "goals.csv",
    "logs.csv",
    "batches.csv",
    "batch_ingredients.csv",
]


def build_backup(output_path: Path) -> list[str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        prefix="shoku_backup_",
        suffix=".zip",
        dir=output_path.parent,
        delete=False,
    ) as tmp_file:
        temp_path = Path(tmp_file.name)

    written_files: list[str] = []
    try:
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for filename in BACKUP_FILES:
                source_path = DATA_DIR / filename
                if source_path.exists():
                    archive.write(source_path, arcname=filename)
                    written_files.append(filename)

        temp_path.replace(output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return written_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a Shoku CSV backup ZIP and replace the previous archive."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Destination ZIP path. Defaults to {DEFAULT_OUTPUT}.",
    )
    args = parser.parse_args()

    written_files = build_backup(args.output.resolve())
    print(f"Wrote {args.output.resolve()} with {len(written_files)} files.")
    for filename in written_files:
        print(f"- {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
