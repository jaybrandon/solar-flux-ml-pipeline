import polars as pl

from src.util import C_CLASS_THRESHOLD

WINDOW_24H = 1440
WINDOW_12H = 720
MIN_FRAC = 0.8
MIN_24H = int(WINDOW_24H * MIN_FRAC)
MIN_12H = int(WINDOW_12H * MIN_FRAC)


def get_feature_expressions() -> tuple:
    return (
        *get_target_expr(),
        *get_lag_expr(),
        *get_rolling_expr(),
        *get_deriv_expr(),
        *get_domain_expr(),
    )


def get_target_expr() -> tuple:
    return (
        pl.col("xrsb_flux")
        .rolling_max(WINDOW_24H, min_samples=MIN_24H)
        .shift(-WINDOW_24H)
        .alias("max_24h_la"),
    )


def get_lag_expr() -> tuple:
    return (
        pl.col("xrsb_flux").shift(15).alias("lag_15"),
        pl.col("xrsb_flux").shift(60).alias("lag_60"),
        pl.col("xrsb_flux").shift(120).alias("lag_120"),
        pl.col("xrsb_flux").shift(1440).alias("lag_1440"),
    )


def get_rolling_expr() -> tuple:
    return (
        pl.col("xrsb_flux")
        .rolling_max(WINDOW_12H, min_samples=MIN_12H)
        .alias("roll_max_720"),
        pl.col("xrsb_flux")
        .rolling_std(WINDOW_12H, min_samples=MIN_12H)
        .alias("roll_std_720"),
        pl.col("xrsb_flux")
        .rolling_mean(WINDOW_12H, min_samples=MIN_12H)
        .alias("roll_mean_720"),
    )


def get_deriv_expr() -> tuple:
    return (
        pl.col("xrsb_flux").diff(5).alias("deriv_1_5"),
        pl.col("xrsb_flux").diff(5).diff(5).alias("deriv_2_5"),
    )


def get_domain_expr() -> tuple:
    return (
        (
            (pl.col("xrsb_flux") >= C_CLASS_THRESHOLD)
            & (pl.col("xrsb_flux").shift(1) < C_CLASS_THRESHOLD)
        )
        .rolling_sum(WINDOW_12H, min_samples=MIN_12H)
        .alias("roll_c_class_cross_720"),
    )
