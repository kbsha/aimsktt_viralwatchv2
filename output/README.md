# Output Join Workflow

This folder contains the merged dataset outputs produced from the repository’s upstream source files.

## Files in this folder

- `insp_sitrep_merged.csv` — wide merged table produced from the INSP SitRep source files.
- `flowminder_merged.csv` — wide merged table produced from the Flowminder source files.

## How the join was done

### 1. INSP SitRep join

The `insp_sitrep` workflow uses the script in `scripts/join_insp_sitrep.py`.

Process:
1. Collect the relevant CSV files into the local workspace.
2. Read each CSV file.
3. Detect the geography key column (`nom`) and the date column.
4. Keep exactly one value column per file.
5. Rename that value column using the file stem so each metric becomes a separate feature.
6. Merge all files on `(nom, date)` using an outer join.
7. Save the final wide table to `output/insp_sitrep_merged.csv`.

### 2. Flowminder join

The Flowminder workflow uses the script in `scripts/join_flowminder.py`.

Process:
1. Collect the downloaded Flowminder CSV files into `data_test/`.
2. Read each file as a two-column geography/value source.
3. Treat the first column as the join key (`nom`).
4. Treat the second column as the feature value.
5. Rename the feature column using the filename stem.
6. Merge all files on `nom` using an outer join.
7. Save the final wide table to `output/flowminder_merged.csv`.

## Notes

- The merge strategy is a wide-table join, so each source file becomes one column in the final dataset.
- Missing combinations remain as `NaN`.
- The key idea for both datasets is the same: one geography identifier plus one feature per input file.

## Reproducible command

The merged outputs were generated with these commands:

```bash
python scripts/join_insp_sitrep.py
python scripts/join_flowminder.py
```
