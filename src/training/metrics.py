import numpy as np
from sklearn.metrics import (
    d2_tweedie_score,
    f1_score,
    precision_score,
    recall_score,
    root_mean_squared_log_error,
)

from src.util import M_CLASS_THRESHOLD, X_CLASS_THRESHOLD


def calc_metrics(
    target: np.ndarray,
    preds: np.ndarray,
    baseline: int | float,
    tweedie_variance_power: float,
    prefix: str = "",
):
    rmsle = root_mean_squared_log_error(target, preds)
    rmsle_baseline = root_mean_squared_log_error(target, np.full(len(target), baseline))

    tweedie_deviance = d2_tweedie_score(target, preds, power=tweedie_variance_power)

    actual_m_class = target >= M_CLASS_THRESHOLD
    pred_m_class = preds >= M_CLASS_THRESHOLD

    f1_m_class = f1_score(actual_m_class, pred_m_class, zero_division=0)
    recall_m_class = recall_score(actual_m_class, pred_m_class, zero_division=0)
    precision_m_class = precision_score(actual_m_class, pred_m_class, zero_division=0)

    actual_x_class = target >= X_CLASS_THRESHOLD
    pred_x_class = preds >= X_CLASS_THRESHOLD

    f1_x_class = f1_score(actual_x_class, pred_x_class, zero_division=0)
    recall_x_class = recall_score(actual_x_class, pred_x_class, zero_division=0)
    precision_x_class = precision_score(actual_x_class, pred_x_class, zero_division=0)

    return {
        f"{prefix}rmsle": rmsle,
        f"{prefix}rmsle_baseline": rmsle_baseline,
        f"{prefix}tweedie_deviance": tweedie_deviance,
        f"{prefix}f1_m_class": f1_m_class,
        f"{prefix}recall_m_class": recall_m_class,
        f"{prefix}precision_m_class": precision_m_class,
        f"{prefix}f1_x_class": f1_x_class,
        f"{prefix}recall_x_class": recall_x_class,
        f"{prefix}precision_x_class": precision_x_class,
    }
