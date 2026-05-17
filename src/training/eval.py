from pathlib import Path

import numpy as np
import polars as pl
import xgboost as xgb

import wandb
from src.training.dataset import INPUT_FEATURES, TARGET, split_train_test
from src.training.metrics import calc_metrics
from src.util import REGISTRY_PATH, load_env, set_seed

MODEL_PATH = Path("model")


def eval(config: dict, boost_rounds: int):
    set_seed(42)

    MODEL_PATH.mkdir(parents=True, exist_ok=True)

    entity = load_env("WANDB_ENTITY")
    project = load_env("WANDB_PROJECT")

    train, test = split_train_test()

    with wandb.init(entity, project, job_type="eval_production", config=config) as run:
        config = run.config.as_dict()

        X_train, X_test = train[INPUT_FEATURES], test[INPUT_FEATURES]
        y_train, y_test = train[TARGET], test[TARGET]

        dtrain = xgb.DMatrix(X_train, label=y_train)
        dtest = xgb.DMatrix(X_test, label=y_test)

        bst_eval = xgb.train(
            config,
            dtrain,
            evals=[(dtest, "eval")],
            num_boost_round=2000,
            early_stopping_rounds=50,
        )

        train_targets = dtrain.get_label()
        rmsle_constant = np.expm1(np.mean(np.log1p(train_targets)))

        test_preds = bst_eval.predict(
            dtest, iteration_range=(0, bst_eval.best_iteration + 1)
        )
        test_targets = dtest.get_label()
        test_metrics = calc_metrics(
            test_targets,
            test_preds,
            rmsle_constant,
            config["tweedie_variance_power"],
            "test_",
        )

        train_preds = bst_eval.predict(
            dtrain, iteration_range=(0, bst_eval.best_iteration + 1)
        )
        train_metrics = calc_metrics(
            train_targets,
            train_preds,
            rmsle_constant,
            config["tweedie_variance_power"],
            "train_",
        )

        run.log({**test_metrics, **train_metrics})

        bst_eval.save_model(MODEL_PATH / "eval.json")

        prod_data = pl.concat([train, test])

        dprod = xgb.DMatrix(prod_data[INPUT_FEATURES], label=prod_data[TARGET])

        bst_prod = xgb.train(
            config,
            dprod,
            num_boost_round=boost_rounds,
        )

        bst_prod.save_model(MODEL_PATH / "model.json")

        artifact = run.log_artifact(MODEL_PATH, type="model")

        run.link_artifact(artifact, REGISTRY_PATH, aliases=["latest", "production"])
