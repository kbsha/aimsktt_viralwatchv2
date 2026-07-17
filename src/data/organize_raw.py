# import os
# import shutil

# EXTERNAL_DIR = "data/external/BDBV2026-Data/build/long"
# RAW_DIR = "data/raw"

# # Make sure raw folder exists
# os.makedirs(RAW_DIR, exist_ok=True)

# # Identify outbreak CSVs in external
# csv_files = [
#     f for f in os.listdir(EXTERNAL_DIR)
#     if f.endswith(".csv") and (
#         f.startswith("insp_sitrep__") or
#         f.startswith("public_health_response__") or
#         f.startswith("grid3_healthsites__") or
#         f.startswith("heathsites__") or
#         f.startswith("worldpop__") or
    
#     )
# ]


# print("Found outbreak CSVs:", csv_files)

# # Move them into raw
# for f in csv_files:
#     src = os.path.join(EXTERNAL_DIR, f)
#     dst = os.path.join(RAW_DIR, f)
#     shutil.copy(src, dst)   # use copy if you want to keep originals
#     print(f"✔ Copied {f} → {RAW_DIR}")
import os
import shutil

EXTERNAL_DIR = "data/external/BDBV2026-Data/build/long"
RAW_DIR = "data/raw/selected"

def organize_raw():
    """
    Identify outbreak CSVs in data/external and copy them into data/raw.
    Always copies files to preserve originals in external.
    """
    os.makedirs(RAW_DIR, exist_ok=True)

    # Identify outbreak CSVs
    # csv_files = [f for f in os.listdir(EXTERNAL_DIR) if f.endswith(".csv")]
    csv_files = [
    f for f in os.listdir(EXTERNAL_DIR)
    if f.endswith(".csv") and f.startswith("insp_sitrep__national_")

]
    print("Found outbreak CSVs:", csv_files)

    # Copy into raw
    for f in csv_files:
        src = os.path.join(EXTERNAL_DIR, f)
        dst = os.path.join(RAW_DIR, f)
        shutil.copy(src, dst)
        print(f"✔ Copied {f} → {RAW_DIR}")

if __name__ == "__main__":
    organize_raw()

