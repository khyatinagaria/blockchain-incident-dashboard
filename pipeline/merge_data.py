import pandas as pd
import glob
import os


def merge_all():
    files = [f for f in glob.glob("data/*.csv") if "master" not in f]
    dfs = []
    for f in files:
        blockchain_name = os.path.basename(f).replace(".csv", "")
        df = pd.read_csv(f)
        df["source_file"] = blockchain_name  # safety column
        dfs.append(df)

    master = pd.concat(dfs, ignore_index=True)
    master.drop_duplicates(subset=["title", "source_file"], inplace=True)
    master.to_csv("data/master.csv", index=False)
    print(f"Master CSV: {len(master)} rows")


if __name__ == "__main__":
    merge_all()
