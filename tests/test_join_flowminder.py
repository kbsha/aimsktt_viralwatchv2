from pathlib import Path

import pandas as pd

from scripts.join_flowminder import join_flowminder_csvs


def test_join_flowminder_csvs_merges_on_zone_and_date(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_path = tmp_path / "output" / "flowminder_merged.csv"

    pd.DataFrame(
        {
            "nom": ["Goma", "Beni"],
            "inflow": [12, 8],
        }
    ).to_csv(input_dir / "flowminder_short_inflow.csv", index=False)

    pd.DataFrame(
        {
            "nom": ["Goma", "Beni"],
            "outflow": [5, 3],
        }
    ).to_csv(input_dir / "flowminder_short_outflow.csv", index=False)

    merged = join_flowminder_csvs(input_dir, output_path)

    assert output_path.exists()
    assert sorted(merged.columns.tolist()) == ["flowminder_short_inflow", "flowminder_short_outflow", "nom"]
    assert merged.loc[merged["nom"] == "Goma", "flowminder_short_inflow"].iloc[0] == 12
    assert merged.loc[merged["nom"] == "Beni", "flowminder_short_outflow"].iloc[0] == 3
