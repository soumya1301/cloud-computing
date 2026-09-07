from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.multioutput import MultiOutputClassifier


VM_TYPE_ORDER = [
    "cpu_intensive",
    "memory_intensive",
    "balanced",
]


class AutoencoderWrapper(BaseEstimator, TransformerMixin):
    def __init__(
        self,
        latent_dim: int = 8,
        hidden_dims: Tuple[int, ...] = (32, 16),
        learning_rate: float = 0.001,
        epochs: int = 50,
        batch_size: int = 32,
        use_pca_fallback: bool = True,
        random_state: int = 42,
    ):
        self.latent_dim = latent_dim
        self.hidden_dims = hidden_dims
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.use_pca_fallback = use_pca_fallback
        self.random_state = random_state
        self._model = None
        self._encoder = None
        self._fallback = None
        self._scaler = StandardScaler()

    def fit(self, X: np.ndarray, y=None):
        X_s = self._scaler.fit_transform(X)
        n_features = X_s.shape[1]
        try:
            from tensorflow import keras
            from tensorflow.keras import layers

            input_layer = keras.Input(shape=(n_features,))
            encoded = input_layer
            for h in self.hidden_dims:
                encoded = layers.Dense(h, activation="relu")(encoded)
            latent = layers.Dense(self.latent_dim, activation="relu", name="latent")(encoded)
            decoded = latent
            for h in reversed(self.hidden_dims):
                decoded = layers.Dense(h, activation="relu")(decoded)
            output_layer = layers.Dense(n_features, activation="linear")(decoded)

            autoencoder = keras.Model(input_layer, output_layer)
            encoder = keras.Model(input_layer, latent)
            autoencoder.compile(
                optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
                loss="mse",
            )
            autoencoder.fit(
                X_s, X_s,
                epochs=self.epochs,
                batch_size=self.batch_size,
                shuffle=True,
                verbose=0,
            )
            self._model = autoencoder
            self._encoder = encoder
            self._fallback = None
        except Exception as exc:
            if not self.use_pca_fallback:
                raise exc
            self._model = None
            self._encoder = None
            self._fallback = PCA(
                n_components=min(self.latent_dim, n_features),
                random_state=self.random_state,
            )
            self._fallback.fit(X_s)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        X_s = self._scaler.transform(X)
        if self._encoder is not None:
            return self._encoder.predict(X_s, verbose=0)
        if self._fallback is not None:
            return self._fallback.transform(X_s)
        raise RuntimeError("AutoencoderWrapper has not been fitted yet.")


class VMTypeClassifier:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.seed = config["split"]["random_seed"]
        self.label_encoder = LabelEncoder()
        self.pipeline = None
        self._history = None

    def _build_pipeline(self):
        ae = AutoencoderWrapper(
            latent_dim=8,
            hidden_dims=(32, 16),
            epochs=40,
            batch_size=32,
            use_pca_fallback=True,
            random_state=self.seed,
        )
        svm = SVC(
            C=1.0,
            kernel="rbf",
            gamma="scale",
            probability=True,
            class_weight="balanced",
            random_state=self.seed,
        )
        return Pipeline(steps=[("autoencoder", ae), ("svm", svm)])

    @staticmethod
    def _features_to_matrix(feature_df: pd.DataFrame) -> np.ndarray:
        cols = [c for c in feature_df.columns if c not in ("job_id", "task_index")]
        X = feature_df[cols].fillna(0.0).values.astype(np.float32)
        return X

    def fit(
        self,
        train_features: pd.DataFrame,
        train_labels: pd.DataFrame,
    ) -> "VMTypeClassifier":
        X_train = self._features_to_matrix(train_features)
        y_raw = train_labels["vm_type"].values
        y_train = self.label_encoder.fit_transform(y_raw)
        self.pipeline = self._build_pipeline()
        self.pipeline.fit(X_train, y_train)
        return self

    def predict(self, feature_df: pd.DataFrame) -> np.ndarray:
        X = self._features_to_matrix(feature_df)
        y_enc = self.pipeline.predict(X)
        return self.label_encoder.inverse_transform(y_enc)

    def predict_proba(self, feature_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        X = self._features_to_matrix(feature_df)
        probs = self.pipeline.predict_proba(X)
        return probs, self.label_encoder.classes_

    def fit_predict(
        self,
        train_features: pd.DataFrame,
        train_labels: pd.DataFrame,
        test_features: pd.DataFrame,
    ) -> Tuple[np.ndarray, np.ndarray]:
        self.fit(train_features, train_labels)
        train_pred = self.predict(train_features)
        test_pred = self.predict(test_features)
        return train_pred, test_pred
