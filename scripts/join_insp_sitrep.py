from pathlib import Path

import pandas as pd


def join_insp_sitrep_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    """
    Join all INSP SitRep CSV files on (nom, date) into a wide table.

    Each file contributes one metric column, named after the filename.
    Missing combinations remain as NaN.
    """
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    csv_files = sorted(input_dir.glob("insp_sitrep*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No insp_sitrep*.csv files found in {input_dir}")

    frames: list[pd.DataFrame] = []
    skipped_files: list[str] = []

    for csv_path in csv_files:
        with csv_path.open("r", encoding="utf-8") as handle:
            first_line = handle.readline().strip().split(",")

        if len(first_line) >= 2 and first_line[0].strip().lower() == "nom" and first_line[1].strip().lower() == "date":
            df = pd.read_csv(csv_path)
        else:
            df = pd.read_csv(csv_path, header=None)
            if df.shape[1] >= 3:
                df = df.iloc[:, :3].copy()
                df.columns = ["nom", "date", "value"]
            else:
                print(f"Skipping {csv_path.name}: expected at least 3 columns")
                skipped_files.append(csv_path.name)
                continue

        if {"nom", "date"}.difference(df.columns):
            print(f"Skipping {csv_path.name}: missing required columns")
            skipped_files.append(csv_path.name)
            continue

        value_columns = [column for column in df.columns if column not in {"nom", "date"}]
        if len(value_columns) != 1:
            raise ValueError(f"{csv_path.name} must contain exactly one value column; found {value_columns}")

        metric_name = csv_path.stem.split("__")[1] if len(csv_path.stem.split("__")) >= 2 else value_columns[0]
        frame = df[["nom", "date", value_columns[0]]].copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame.rename(columns={value_columns[0]: metric_name}, inplace=True)
        frames.append(frame)

    if not frames:
        raise RuntimeError(f"No frames to merge. Skipped files: {skipped_files}")

    merged = frames[0]
    for frame in frames[1:]:
        merged = pd.merge(merged, frame, on=["nom", "date"], how="outer")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_dir = repo_root / "data" / "external" / "BDBV2026-Data" / "build" / "long"
    output_path = repo_root / "output" / "insp_sitrep_merged.csv"

    merged = join_insp_sitrep_csvs(input_dir, output_path)
    print(f"Wrote {len(merged)} rows to {output_path}")
    print(f"Health zones (unique nom): {merged['nom'].nunique()}")
    date_series = pd.to_datetime(merged["date"], errors="coerce")
    print(f"Date range: {date_series.min().date() if date_series.notna().any() else 'NA'} to {date_series.max().date() if date_series.notna().any() else 'NA'}")
    print("Missing values per column:")
    print(merged.isna().sum())
    print("Preview:")
    print(merged.head())


if __name__ == "__main__":
    main()
