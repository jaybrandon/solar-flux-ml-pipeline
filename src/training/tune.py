from datetime import datetime, timedelta

import numpy as np
import optuna
import polars as pl
import xgboost as xgb
from optuna.integration.wandb import WeightsAndBiasesCallback

import wandb
from src.training.dataset import INPUT_FEATURES, TARGET, split_train_test
from src.training.metrics import calc_metrics
from src.util import load_env


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


def optimize_params():
    wandb_kwargs = {
        "project": load_env("WANDB_PROJECT"),
        "entity": load_env("WANDB_ENTITY"),
        "group": "hyperparameter_optimization",
    }

    wandbc = WeightsAndBiasesCallback(
        metric_name="val_tweedie_deviance", wandb_kwargs=wandb_kwargs, as_multirun=True
    )

    @wandbc.track_in_wandb()
    def cross_validate(trial: optuna.Trial):
        params = {
            "objective": "reg:tweedie",
            "tweedie_variance_power": trial.suggest_float(
                "tweedie_variance_power", 1.1, 1.9
            ),
            "eta": trial.suggest_float("eta", 0.005, 0.3, log=True),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "max_depth": trial.suggest_int("max_depth", 2, 6),
            "min_child_weight": trial.suggest_int("min_child_weight", 5, 20),
            "subsample": trial.suggest_float("subsample", 0.5, 0.8),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 0.8),
            "lambda": trial.suggest_float("lambda", 0.0, 2.0),
            "alpha": trial.suggest_float("alpha", 0.0, 2.0),
        }

        train, _ = split_train_test()

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
                params,
                dtrain,
                evals=[(dval, "eval")],
                num_boost_round=2000,
                early_stopping_rounds=50,
                verbose_eval=False,
            )

            train_targets = dtrain.get_label()
            rmsle_constant = np.expm1(np.mean(np.log1p(train_targets)))

            val_preds = bst.predict(dval, iteration_range=(0, bst.best_iteration + 1))
            val_targets = dval.get_label()
            val_metrics = calc_metrics(
                val_targets,
                val_preds,
                rmsle_constant,
                params["tweedie_variance_power"],
                "val_",
            )

            train_preds = bst.predict(
                dtrain, iteration_range=(0, bst.best_iteration + 1)
            )
            train_metrics = calc_metrics(
                train_targets,
                train_preds,
                rmsle_constant,
                params["tweedie_variance_power"],
                "train_",
            )

            fold_metrics = {
                **val_metrics,
                **train_metrics,
                "boost_rounds": bst.best_iteration,
            }

            results.append(fold_metrics)

            wandb.log({f"fold_{i}/{key}": value for key, value in fold_metrics.items()})

            current_max_time = test_start - timedelta(minutes=1)

        df_results = pl.DataFrame(results)

        result_dict = df_results.mean().to_dicts()[0]
        std_result_dict = (
            df_results.select(pl.all().name.suffix("_std")).std().to_dicts()[0]
        )

        wandb.log(result_dict)
        wandb.log(std_result_dict)

        trial.set_user_attr("objective", params["objective"])
        trial.set_user_attr("boost_rounds", result_dict["boost_rounds"])

        return result_dict["val_tweedie_deviance"]

    study = optuna.create_study(direction="maximize")
    study.optimize(cross_validate, n_trials=20, callbacks=[wandbc])

    best_params = study.best_params
    best_params["objective"] = study.best_trial.user_attrs["objective"]

    wandb.finish()

    return best_params, int(study.best_trial.user_attrs["boost_rounds"])
