"""Reproducibility utilities: logging, seeding, experiment IDs, JSON I/O."""

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the package logger. Safe to call multiple times."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return logging.getLogger("financial_copilot")


def set_seed(seed: int) -> None:
    """Seed every source of randomness this package currently uses."""
    random.seed(seed)
    np.random.seed(seed)


def new_experiment_id(config_name: str) -> str:
    """A sortable, collision-resistant experiment ID: <config>-<utc timestamp>-<random suffix>."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{config_name}-{stamp}-{uuid.uuid4().hex[:8]}"


def save_json(obj: BaseModel | list | dict, path: str | Path) -> None:
    """Serialize a Pydantic model (or plain JSON-able object) to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: Any = obj.model_dump(mode="json") if isinstance(obj, BaseModel) else obj
    path.write_text(json.dumps(data, indent=2, default=str))


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())
