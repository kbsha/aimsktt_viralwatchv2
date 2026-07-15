from pathlib import Path

import pandas as pd


def _read_flowminder_frame(csv_path: Path) -> pd.DataFrame | None:
    """Read one Flowminder CSV as a two-column geography/value frame."""
    with csv_path.open("r", encoding="utf-8") as handle:
        first_line = handle.readline().strip().split(",")

    header_row = (
        len(first_line) >= 2
        and first_line[0].strip().lower() in {"nom", "zone_de_sante", "zone_sante", "zone"}
        and first_line[1].strip().lower() in {"value", "inflow", "outflow", "date"}
    )

    if header_row:
        frame = pd.read_csv(csv_path)
    else:
        frame = pd.read_csv(csv_path, header=None)
        if frame.shape[1] < 2:
            return None
        frame = frame.iloc[:, :2].copy()
        frame.columns = ["nom", "value"]

    if frame.shape[1] < 2:
        return None

    frame = frame.iloc[:, :2].copy()
    frame.columns = ["nom", "value"]
    return frame


def join_flowminder_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    """
    Join Flowminder files on the geography key (`nom`) and build a wide feature table.

    Each input file contributes a single feature column named from the CSV filename.
    Missing combinations stay as NaN.
    """
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    csv_files = sorted(input_dir.glob("flowminder*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No flowminder*.csv files found in {input_dir}")

    frames: list[pd.DataFrame] = []
    skipped_files: list[str] = []

    for csv_path in csv_files:
        frame = _read_flowminder_frame(csv_path)
        if frame is None:
            print(f"Skipping {csv_path.name}: expected at least 2 columns")
            skipped_files.append(csv_path.name)
            continue

        feature_name = csv_path.stem
        feature_frame = frame[["nom", "value"]].copy()
        feature_frame.rename(columns={"value": feature_name}, inplace=True)
        frames.append(feature_frame)

    if not frames:
        raise RuntimeError(f"No frames to merge. Skipped files: {skipped_files}")

    merged = frames[0]
    join_col = "nom"
    for frame in frames[1:]:
        merged = pd.merge(merged, frame, on=join_col, how="outer")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_dir = repo_root / "data_test"
    output_path = repo_root / "output" / "flowminder_merged.csv"

    merged = join_flowminder_csvs(input_dir, output_path)
    print(f"Wrote {len(merged)} rows to {output_path}")
    print(f"Health zones (unique nom): {merged['nom'].nunique()}")
    print("Missing values per column:")
    print(merged.isna().sum())
    print("Preview:")
    print(merged.head())


if __name__ == "__main__":
    main()
