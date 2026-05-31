from src.training.eval import eval
from src.training.tune import optimize_params
from src.util import set_seed


def train():
    set_seed(42)

    params, boost_rounds = optimize_params()

    eval(params, boost_rounds)


if __name__ == "__main__":
    train()
