import optuna

from src.training.eval import eval
from src.training.tune import cross_validate
from src.util import set_seed


def train():
    set_seed(42)

    study = optuna.create_study(direction="maximize")
    study.optimize(
        lambda trial: cross_validate(trial, study.study_name), n_trials=20, timeout=600
    )

    best_params = study.best_params
    best_params["objective"] = study.best_trial.user_attrs["objective"]
    eval(best_params, int(study.best_trial.user_attrs["boost_rounds"]))


if __name__ == "__main__":
    train()
