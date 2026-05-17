from datetime import datetime, timedelta

import numpy as np
import polars as pl
import xgboost as xgb

import wandb
from src.training.dataset import INPUT_FEATURES, TARGET, split_train_test
from src.training.metrics import calc_metrics
from src.util import load_env, set_seed

SWEEP_CONFIG = {
    "method": "bayes",
    "metric": {"name": "val_tweedie_deviance", "goal": "maximize"},
    "parameters": {
        "objective": {"value": "reg:tweedie"},
        "tweedie_variance_power": {"min": 1.1, "max": 1.9},
        "eta": {"distribution": "log_uniform_values", "min": 0.005, "max": 0.3},
        "gamma": {"min": 0.0, "max": 5.0},
        "max_depth": {"min": 2, "max": 6},
        "min_child_weight": {"min": 5, "max": 20},
        "subsample": {"min": 0.5, "max": 0.8},
        "colsample_bytree": {"min": 0.5, "max": 0.8},
        "lambda": {"min": 0.0, "max": 2.0},
        "alpha": {"min": 0.0, "max": 2.0},
    },
}


def ts_split(
    df: pl.DataFrame, max_time: datetime, test_start: datetime, gap: timedelta
) -> tuple[xgb.DMatrix, xgb.DMatrix]:
    train_end = test_start - gap

    val = df.filter((pl.col("time") >= test_start) & (pl.col("time") <= max_time))
    X_val = val.select(pl.col(INPUT_FEATURES))
    y_val = val.select(pl.col(TARGET))

    train = df.filter(pl.col("time") < train_end)
    X_train = train.select(pl.col(INPUT_FEATURES))
    y_train = train.select(pl.col(TARGET))

    return xgb.DMatrix(X_train, label=y_train), xgb.DMatrix(X_val, label=y_val)


def cross_validate():
    set_seed(42)

    entity = load_env("WANDB_ENTITY")
    project = load_env("WANDB_PROJECT")

    train, _ = split_train_test()

    with wandb.init(entity, project) as run:
        config = run.config

        min_time = train.select(pl.col("time").min()).item()
        max_time = train.select(pl.col("time").max()).item()

        n_splits = 5
        test_duration = (max_time - min_time) // (2 * n_splits)
        gap = timedelta(minutes=1440)
        current_max_time = max_time

        results = []

        for i in range(n_splits):
            test_start = (current_max_time - test_duration).replace(
                second=0, microsecond=0
            )

            dtrain, dval = ts_split(train, current_max_time, test_start, gap)

            bst = xgb.train(
                config.as_dict(),
                dtrain,
                evals=[(dval, "eval")],
                num_boost_round=2000,
                early_stopping_rounds=50,
            )

            train_targets = dtrain.get_label()
            rmsle_constant = np.expm1(np.mean(np.log1p(train_targets)))

            val_preds = bst.predict(dval, iteration_range=(0, bst.best_iteration + 1))
            val_targets = dval.get_label()
            val_metrics = calc_metrics(
                val_targets,
                val_preds,
                rmsle_constant,
                config.tweedie_variance_power,
                "val_",
            )

            train_preds = bst.predict(
                dtrain, iteration_range=(0, bst.best_iteration + 1)
            )
            train_metrics = calc_metrics(
                train_targets,
                train_preds,
                rmsle_constant,
                config.tweedie_variance_power,
                "train_",
            )

            fold_metrics = {
                **val_metrics,
                **train_metrics,
                "boost_rounds": bst.best_iteration,
            }

            results.append(fold_metrics)

            run.log({f"fold_{i}/{key}": value for key, value in fold_metrics.items()})

            current_max_time = test_start - timedelta(minutes=1)

        df_results = pl.DataFrame(results)

        run.log(df_results.mean().to_dicts()[0])


if __name__ == "__main__":
    cross_validate()
