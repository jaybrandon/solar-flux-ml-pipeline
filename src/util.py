import os
import random

import numpy as np

REGISTRY_PATH = "wandb-registry-model/solar-flare-xgboost"
MULTIPLIER = 1000000
C_CLASS_THRESHOLD = 1e-6 * MULTIPLIER
M_CLASS_THRESHOLD = 1e-5 * MULTIPLIER
X_CLASS_THRESHOLD = 1e-4 * MULTIPLIER


def set_seed(seed: int = 42):
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    np.random.seed(seed)


def load_env(key: str) -> str:
    env = os.environ.get(key)
    if not env:
        raise ValueError(f"{key} environment variable is not set")
    return env
