import numpy as np


_DIFF = {"easy": 0.0, "medium": 0.5, "hard": 1.0}

def build_feature_vector(mastery: float, attempts: int, difficulty: str) -> np.ndarray:
    return np.array([mastery, min(attempts, 20) / 20.0, _DIFF[difficulty], 1.0])

