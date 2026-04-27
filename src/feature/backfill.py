import os
import re
import tempfile

import feature_extraction as feat
import polars as pl
import requests
import xarray as xr
from tqdm import tqdm


def backfill_data():
    feature_store_uri = os.environ.get("FEATURE_STORE_URI")
    if not feature_store_uri:
        raise ValueError("FEATURE_STORE_URI environment variable is not set")

    base_url = "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/goes18/l2/data/xrsf-l2-avg1m_science/"

    r = requests.get(base_url)
    r.raise_for_status()

    pattern = r"sci_xrsf-l2-avg1m_g18_s20220617_e\d{8}_v[\d\-]+\.nc"
    matches = re.findall(pattern, r.text)

    if not matches:
        raise ValueError("Error: Backfill file not found.")

    dl_url = base_url + matches[0]
    print(f"Downloading latest archive: {matches[0]}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".nc") as tmp_file:
        with requests.get(dl_url, stream=True) as r:
            r.raise_for_status()

            byte_size = int(r.headers.get("content-length", 0))
            prog = tqdm(
                total=byte_size,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
                desc="Downloading data...",
            )

            for chunk in r.iter_content(chunk_size=1024 * 1024):
                tmp_file.write(chunk)
                prog.update(len(chunk))
            prog.close()

        temp_path = tmp_file.name

    ds = xr.open_dataset(temp_path)

    df = pl.from_pandas(
        ds[["xrsb_flux", "xrsb_flag", "electron_correction_flag"]].to_pandas(),
        include_index=True,
    )

    ds.close()
    os.remove(temp_path)

    lf = df.lazy()

    # Null invalid flux values
    lf = lf.with_columns(
        pl.when(
            ((pl.col("xrsb_flag").cast(pl.Int32) & 2) == 2)
            | ((pl.col("xrsb_flag").cast(pl.Int32) & 1) == 1)
        )
        .then(None)
        .when(
            ((pl.col("electron_correction_flag").cast(pl.Int32) & 1) == 1)
            | ((pl.col("electron_correction_flag").cast(pl.Int32) & 16) == 16)
        )
        .then(None)
        .otherwise(pl.col("xrsb_flux"))
        .alias("xrsb_flux")
    )

    # Forward fill null values
    lf = lf.select(
        pl.col("time"), pl.col("xrsb_flux").fill_null(strategy="forward", limit=10)
    )

    # Feature extraction
    lf = lf.with_columns(*feat.get_feature_expressions())

    # Drop null rows
    lf = lf.drop_nulls()

    # Add year and month for partitioning
    lf = lf.with_columns(
        pl.col("time").dt.year().alias("year"),
        pl.col("time").dt.month().alias("month"),
    )

    df = lf.collect()

    assert isinstance(df, pl.DataFrame), "Expected DataFrame, got InProcessQuery"

    df.write_parquet(f"{feature_store_uri}/", partition_by=["year", "month"])


if __name__ == "__main__":
    backfill_data()
