import pandas as pd
import glob
import os


def merge_all():
    files = [f for f in glob.glob("data/*.csv") if "master" not in f]
    dfs = []
    for f in files:
        blockchain_name = os.path.basename(f).replace(".csv", "")
        df = pd.read_csv(f)
        df["source_file"] = blockchain_name

        # Normalize column names — handle both old and new scraper output
        if "report_title" in df.columns:
            df = df.rename(columns={
                "report_title":                "title",
                "overall_theme_tags":          "theme_tags",
                "technology_used":             "tech",
                "date_of_report":              "date",
                "scam_category":               "type_of_malicious_activity",
                "report_url":                  "article_url",
                "report_description":          "description",
                "report_related_links":        "links",
                "report_related_image_link":   "image_link",
                "report_extraction_timestamp": "extraction_timestamp",
            })

        dfs.append(df)

    master = pd.concat(dfs, ignore_index=True)
    master.drop_duplicates(subset=["title", "source_file"], inplace=True)
    master.to_csv("data/master.csv", index=False)
    print(f"Master CSV: {len(master)} rows")


if __name__ == "__main__":
    merge_all()
