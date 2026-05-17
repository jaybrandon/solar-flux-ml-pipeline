import wandb
from src.training.eval import eval
from src.training.tune import SWEEP_CONFIG, cross_validate
from src.util import load_env


def train():
    entity = load_env("WANDB_ENTITY")
    project = load_env("WANDB_PROJECT")

    sweep_id = wandb.sweep(SWEEP_CONFIG, entity, project)

    wandb.agent(sweep_id, function=cross_validate, count=20)

    api = wandb.Api()
    sweep = api.sweep(f"{entity}/{project}/{sweep_id}")
    sweep.state = "Finished"
    best_run = sweep.best_run()

    eval(best_run.config, int(best_run.summary_metrics["boost_rounds"]))


if __name__ == "__main__":
    train()
