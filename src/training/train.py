from src.training.dataset import split_train_test
from src.training.eval import eval
from src.training.tune import optimize_params
from src.util import set_seed


def train():
    set_seed(42)

    train_df, test_df = split_train_test()

    params, boost_rounds = optimize_params(train_df)

    eval(train_df, test_df, params, boost_rounds)


if __name__ == "__main__":
    train()
