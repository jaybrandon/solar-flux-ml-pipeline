from contextlib import asynccontextmanager
from pathlib import Path

import polars as pl
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import wandb
from src.training.dataset import INPUT_FEATURES
from src.util import M_CLASS_THRESHOLD, MULTIPLIER, REGISTRY_PATH, load_env


class Input(BaseModel):
    xrsb_flux: float
    lag_15: float
    lag_60: float
    lag_120: float
    lag_1440: float
    roll_max_720: float
    roll_std_720: float
    roll_mean_720: float
    deriv_1_5: float
    deriv_2_5: float
    roll_c_class_cross_720: int


model_data = {}
online_fs_uri: str


def load_model():
    entity = load_env("WANDB_ENTITY")
    project = load_env("WANDB_PROJECT")
    global online_fs_uri
    online_fs_uri = load_env("ONLINE_FS_URI")

    api = wandb.Api(overrides={"entity": entity, "project": project})
    artifact_path = REGISTRY_PATH + ":production"

    artifact: wandb.Artifact = api.artifact(artifact_path)

    if (
        "metadata" in model_data
        and model_data["metadata"]["version"] == artifact.version
    ):
        return False  # No new model to load

    artifact_dir = Path(artifact.download())

    bst = xgb.Booster(model_file=artifact_dir / "model.json")

    model_data["model"] = bst

    metadata: dict[str, str | list[str] | dict] = {
        "artifact_name": artifact.name,
        "version": artifact.version,
        "aliases": artifact.aliases,
        "created_at": artifact.created_at,
    }

    run = artifact.logged_by()
    if run:
        metadata["run_id"] = run.id
        metadata["metrics"] = run.summary_metrics

    model_data["metadata"] = metadata

    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/reload")
def reload_model():
    try:
        if load_model():
            return {"status": "success", "message": "Model reloaded successfully"}
        else:
            return {"status": "success", "message": "No new model loaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ready")
def readiness_probe():
    if "model" not in model_data:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if "metadata" not in model_data:
        raise HTTPException(status_code=503, detail="Model metadata not loaded")
    return {"status": "ready"}


@app.get("/predictions/latest")
def get_predictions_latest():
    df = pl.read_parquet(f"{online_fs_uri}/*.parquet")
    return predict(df)


@app.post("/predict")
def post_predict(input: Input):
    df = pl.DataFrame(input.model_dump())
    df = df.with_columns(pl.col(pl.Float64) * MULTIPLIER)
    return predict(df)


def predict(df: pl.DataFrame):
    dinf = xgb.DMatrix(df[INPUT_FEATURES])
    pred = float(model_data["model"].predict(dinf)[0])

    return {
        "predicted_max_flux_24h": pred / MULTIPLIER,
        "m_class_alert": pred >= M_CLASS_THRESHOLD,
        "model_version": model_data["metadata"]["version"],
        "wandb_run_id": model_data["metadata"]["run_id"]
        if "run_id" in model_data["metadata"]
        else None,
    }
