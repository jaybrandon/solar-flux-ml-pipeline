from datetime import timedelta

import polars as pl

from src.util import load_env

TARGET = "max_24h_la"
INPUT_FEATURES = [
    "xrsb_flux",
    "lag_15",
    "lag_60",
    "lag_120",
    "lag_1440",
    "roll_max_720",
    "roll_std_720",
    "roll_mean_720",
    "deriv_1_5",
    "deriv_2_5",
    "roll_c_class_cross_720",
]


def get_data():
    bucket = load_env("OFFLINE_FS_URI")

    lf = pl.scan_parquet(f"{bucket}/")

    return lf


def split_train_test():
    lf = get_data()

    min_time = lf.select(pl.col("time").min()).collect().item()
    max_time = lf.select(pl.col("time").max()).collect().item()

    test_duration = (max_time - min_time) * 0.2
    test_start = (max_time - test_duration).replace(second=0, microsecond=0)
    # Add 24h gap to avoid data leakage
    train_end = test_start - timedelta(minutes=1440)

    test_set = lf.filter(pl.col("time") >= test_start).collect()
    train_set = lf.filter(pl.col("time") < train_end).collect()

    return train_set, test_set
