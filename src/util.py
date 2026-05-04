import os
import random

import numpy as np


def set_seed(seed: int = 42):
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    np.random.seed(seed)


def load_env(key: str) -> str:
    env = os.environ.get(key)
    if not env:
        raise ValueError(f"{key} environment variable is not set")
    return env
