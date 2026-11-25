"""
Machine Learning Workload Predictor Model.
Compares Random Forest Regressor and Gradient Boosting / HistGradientBoosting
to predict expected execution time of genomic regions during coverage computation.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class WorkloadPredictor:
    def __init__(self,
                 model_type: str = "random_forest",
                 n_estimators: int = 100,
                 max_depth: Optional[int] = 12,
                 random_state: int = 42):
        self.model_type = model_type.lower()
        self.random_state = random_state
        self.feature_columns: List[str] = [
            "sampled_read_count",
            "read_density",
            "estimated_mean_depth",
            "cigar_mismatch_rate",
            "indel_frequency",
            "mean_mapq",
            "gc_content",
            "region_span"
        ]
        
        if self.model_type == "random_forest":
            self.model = RandomForestRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=random_state,
                n_jobs=-1
            )
        elif self.model_type in ("gradient_boosting", "catboost_equivalent"):
            self.model = HistGradientBoostingRegressor(
                max_iter=n_estimators,
                max_depth=max_depth,
                random_state=random_state
            )
        else:
            raise ValueError(f"Unknown model_type: {model_type}")
            
        self.is_trained = False
        self.evaluation_metrics: Dict[str, float] = {}
        self.feature_importances_: Dict[str, float] = {}

    def train(self,
              df: pd.DataFrame,
              target_col: str = "execution_time_ms",
              test_size: float = 0.2) -> Dict[str, float]:
        """
        Trains the workload regression model and records performance metrics.
        """
        X = df[self.feature_columns].copy()
        y = df[target_col].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state
        )

        self.model.fit(X_train, y_train)
        self.is_trained = True

        y_pred = self.model.predict(X_test)
        
        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2 = float(r2_score(y_test, y_pred))

        # 5-fold cross-validation RMSE
        cv = KFold(n_splits=min(5, len(df)), shuffle=True, random_state=self.random_state)
        cv_scores = cross_val_score(self.model, X, y, cv=cv, scoring="neg_root_mean_squared_error")
        cv_rmse = float(-cv_scores.mean())

        self.evaluation_metrics = {
            "MAE": round(mae, 4),
            "RMSE": round(rmse, 4),
            "R2": round(r2, 4),
            "CV_RMSE": round(cv_rmse, 4)
        }

        # Calculate feature importances if available
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            self.feature_importances_ = {
                feat: float(round(imp, 4))
                for feat, imp in zip(self.feature_columns, importances)
            }
        else:
            self.feature_importances_ = {feat: 1.0 / len(self.feature_columns) for feat in self.feature_columns}

        return self.evaluation_metrics

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predicts computational workload (execution time in ms) for given regions.
        """
        if not self.is_trained:
            raise RuntimeError("Model has not been trained yet.")
        X = df[self.feature_columns].copy()
        predictions = self.model.predict(X)
        return np.maximum(predictions, 0.1)  # Ensure positive execution time

    def save(self, filepath: str) -> None:
        """
        Saves the trained model to disk.
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump({
            "model": self.model,
            "feature_columns": self.feature_columns,
            "metrics": self.evaluation_metrics,
            "feature_importances": self.feature_importances_,
            "model_type": self.model_type
        }, filepath)

    @classmethod
    def load(cls, filepath: str) -> "WorkloadPredictor":
        """
        Loads a trained model from disk.
        """
        data = joblib.load(filepath)
        instance = cls(model_type=data.get("model_type", "random_forest"))
        instance.model = data["model"]
        instance.feature_columns = data["feature_columns"]
        instance.evaluation_metrics = data.get("metrics", {})
        instance.feature_importances_ = data.get("feature_importances", {})
        instance.is_trained = True
        return instance
