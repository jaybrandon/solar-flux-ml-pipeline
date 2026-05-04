from datetime import timedelta
from io import BytesIO

import feature_extraction as feat
import polars as pl
import requests

from src.util import load_env


def store_offline_features(lf: pl.LazyFrame, offline_fs_uri: str):
    # Drop null rows for offline fs
    lf = lf.drop_nulls()

    # Add year and month for partitioning
    lf = lf.with_columns(
        pl.col("time").dt.year().alias("year"),
        pl.col("time").dt.month().alias("month"),
    )

    df = lf.collect()

    partitions = df.partition_by(["year", "month"], as_dict=True)  # ty: ignore[unresolved-attribute]

    for (year, month), partition_df in partitions.items():
        batch_timestamp = (
            partition_df.select(pl.col("time").min()).item().strftime("%Y%m%d_%H%M%S")
        )

        file = f"{offline_fs_uri}/year={year}/month={month}/batch_{batch_timestamp}.parquet"
        partition_df.write_parquet(file)

        print("Saved " + file)


def store_online_features(lf: pl.LazyFrame, online_fs_uri: str):
    latest = lf.filter(pl.col("time") == pl.col("time").max()).collect()

    file = f"{online_fs_uri}/feature.parquet"
    latest.write_parquet(file)  # ty: ignore[unresolved-attribute]

    print("Saved " + file)


def process_batch():
    online_fs_uri = load_env("ONLINE_FS_URI")
    offline_fs_uri = load_env("OFFLINE_FS_URI")

    url = "https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json"
    r = requests.get(url)
    r.raise_for_status()

    energy = pl.Enum(["0.05-0.4nm", "0.1-0.8nm"])

    # Load batch data
    batch_lf = pl.read_json(
        BytesIO(r.content), schema_overrides={"energy": energy, "flux": pl.Float32}
    ).lazy()

    # Filter for b flux
    batch_lf = batch_lf.filter(pl.col("energy") == "0.1-0.8nm")

    # Convert necessary columns
    batch_lf = batch_lf.select(
        pl.col("time_tag")
        .str.to_datetime("%Y-%m-%dT%H:%M:%SZ", time_unit="ns")
        .alias("time"),
        pl.col("flux").alias("xrsb_flux"),
    )

    # Load offline data for feature calculation
    history_lf = pl.scan_parquet(offline_fs_uri)

    latest_history_time = history_lf.select(pl.col("time").max()).collect().item()  # ty: ignore[unresolved-attribute]

    batch_lf = batch_lf.filter(pl.col("time") > latest_history_time)

    earliest_op_time = batch_lf.select(pl.col("time").min()).collect().item()  # ty: ignore[unresolved-attribute]

    cutoff_time = earliest_op_time - timedelta(minutes=1440)

    history_lf = history_lf.filter(
        (pl.col("time") >= cutoff_time) & (pl.col("time") <= latest_history_time)
    ).select(pl.col("time"), pl.col("xrsb_flux"))

    # Merge batch with history data
    merge_lf = pl.concat([history_lf, batch_lf])

    # Ensure consistency
    merge_lf = merge_lf.collect().upsample("time", every="1m").lazy()  # ty: ignore[unresolved-attribute]
    merge_lf = merge_lf.select(
        pl.col("time"), pl.col("xrsb_flux").fill_null(strategy="forward", limit=10)
    )

    # Feature extraction
    merge_lf = merge_lf.with_columns(*feat.get_feature_expressions())

    # Remove history rows
    merge_lf = merge_lf.filter(pl.col("time") >= earliest_op_time)

    store_online_features(merge_lf, online_fs_uri)

    store_offline_features(merge_lf, offline_fs_uri)


if __name__ == "__main__":
    process_batch()
