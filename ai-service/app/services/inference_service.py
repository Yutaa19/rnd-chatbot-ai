import os
import numpy as np
import joblib
import tensorflow as tf
from typing import Optional

# ── Hyperparameter harus sama persis dengan notebook ──────────────────────────
WINDOW_SIZE = 14
HORIZON     = 7

# ── Path ke artifact (relatif dari working dir container = /app) ──────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH  = os.path.join(BASE_DIR, "caffeinance_lstm.keras")
SCALER_PATH = os.path.join(BASE_DIR, "caffeinance_scaler.pkl")

# ── Singleton: model & scaler di-load sekali, disimpan di sini ───────────────
_model  = None
_scaler = None


# ══════════════════════════════════════════════════════════════════════════════
# Custom classes — WAJIB ada agar load_model tidak error
# Definisi ini harus identik 100% dengan yang ada di notebook
# ══════════════════════════════════════════════════════════════════════════════

class ResidualLSTMLayer(tf.keras.layers.Layer):
    def __init__(self, units, dropout_rate=0.2, **kwargs):
        super().__init__(**kwargs)
        self.units        = units
        self.dropout_rate = dropout_rate
        self.lstm         = tf.keras.layers.LSTM(units, return_sequences=True)
        self.bn           = tf.keras.layers.BatchNormalization()
        self.dropout      = tf.keras.layers.Dropout(dropout_rate)
        self.dense        = tf.keras.layers.Dense(units, activation='relu')

    def call(self, inputs, training=False):
        x        = self.lstm(inputs)
        x        = self.bn(x, training=training)
        x        = self.dropout(x, training=training)
        residual = self.dense(inputs)
        return x + residual

    def get_config(self):
        config = super().get_config()
        config.update({'units': self.units, 'dropout_rate': self.dropout_rate})
        return config


class CaffeinanceLSTM(tf.keras.Model):
    def __init__(self, units=32, horizon=7, dropout_rate=0.2, **kwargs):
        super().__init__(**kwargs)
        self.units        = units
        self.horizon      = horizon
        self.dropout_rate = dropout_rate
        self.lstm1        = ResidualLSTMLayer(units, dropout_rate)
        self.lstm2        = ResidualLSTMLayer(units, dropout_rate)
        self.output_layer = tf.keras.layers.Dense(horizon, activation='sigmoid')

    def call(self, inputs, training=False):
        x = self.lstm1(inputs, training=training)
        x = self.lstm2(x,      training=training)
        x = x[:, -1, :]
        return self.output_layer(x)

    def get_config(self):
        config = super().get_config()
        config.update({
            'units':        self.units,
            'horizon':      self.horizon,
            'dropout_rate': self.dropout_rate,
        })
        return config


class AsimetrisHuberLoss(tf.keras.losses.Loss):
    def __init__(self, delta=0.1, alpha=2.0, **kwargs):
        super().__init__(**kwargs)
        self.delta = delta
        self.alpha = alpha

    def call(self, y_true, y_pred):
        error     = y_true - y_pred
        abs_error = tf.abs(error)
        huber = tf.where(
            abs_error <= self.delta,
            0.5 * tf.square(error),
            self.delta * (abs_error - 0.5 * self.delta)
        )
        weight = tf.where(error < 0, self.alpha, 1.0)
        return tf.reduce_mean(weight * huber)

    def get_config(self):
        config = super().get_config()
        config.update({'delta': self.delta, 'alpha': self.alpha})
        return config


# ══════════════════════════════════════════════════════════════════════════════
# Load model — dipanggil sekali saat FastAPI startup via lifespan
# ══════════════════════════════════════════════════════════════════════════════

def load_model_and_scaler() -> None:
    """
    Load model dan scaler ke memory.
    Panggil fungsi ini di dalam blok lifespan FastAPI (sebelum yield).
    """
    global _model, _scaler

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model tidak ditemukan di: {MODEL_PATH}\n"
            "Pastikan caffeinance_lstm.keras sudah ada di root folder ai-service/"
        )
    if not os.path.exists(SCALER_PATH):
        raise FileNotFoundError(
            f"Scaler tidak ditemukan di: {SCALER_PATH}\n"
            "Pastikan caffeinance_scaler.pkl sudah ada di root folder ai-service/"
        )

    _model = tf.keras.models.load_model(
        MODEL_PATH,
        custom_objects={
            'ResidualLSTMLayer':  ResidualLSTMLayer,
            'CaffeinanceLSTM':    CaffeinanceLSTM,
            'AsimetrisHuberLoss': AsimetrisHuberLoss,
        }
    )
    _scaler = joblib.load(SCALER_PATH)
    print("✅ Caffeinance LSTM model loaded successfully.")
    print("✅ Scaler loaded successfully.")


def is_model_ready() -> bool:
    return _model is not None and _scaler is not None


# ══════════════════════════════════════════════════════════════════════════════
# Inference
# ══════════════════════════════════════════════════════════════════════════════

def _derive_trend(pred_rupiah: np.ndarray) -> tuple[str, float]:
    """
    Konversi array 7 prediksi harian → (forecast_trend, forecast_percentage).

    Logika:
      - Bandingkan rata-rata 3 hari pertama vs 3 hari terakhir prediksi
      - Threshold ±3% untuk menentukan NAIK / TURUN / STABIL
    """
    avg_first = pred_rupiah[:3].mean()
    avg_last  = pred_rupiah[-3:].mean()

    if avg_first == 0:
        return "STABIL", 0.0

    change_pct = ((avg_last - avg_first) / avg_first) * 100

    if change_pct > 3:
        trend = "NAIK"
    elif change_pct < -3:
        trend = "TURUN"
    else:
        trend = "STABIL"

    return trend, round(abs(change_pct), 1)


def predict_cashflow(historical_sales: list) -> Optional[dict]:
    """
    Jalankan inference LSTM.

    Args:
        historical_sales: list nilai total_sales harian (minimal WINDOW_SIZE=14 nilai)

    Returns:
        dict berisi forecast_trend, forecast_percentage, dan predictions per hari.
        None jika model belum di-load.

    Raises:
        ValueError: jika data historis kurang dari WINDOW_SIZE hari.
    """
    if not is_model_ready():
        return None

    if len(historical_sales) < WINDOW_SIZE:
        raise ValueError(
            f"Minimal {WINDOW_SIZE} hari data historis diperlukan. "
            f"Diterima: {len(historical_sales)} hari."
        )

    # Ambil WINDOW_SIZE hari terakhir → scale → reshape untuk LSTM
    recent_data   = np.array(historical_sales[-WINDOW_SIZE:]).reshape(-1, 1)
    recent_scaled = _scaler.transform(recent_data)
    X_input       = recent_scaled.reshape(1, WINDOW_SIZE, 1).astype(np.float32)

    # Prediksi (scaled 0-1) → inverse transform → rupiah
    pred_scaled = _model.predict(X_input, verbose=0)[0]
    pred_rupiah = _scaler.inverse_transform(pred_scaled.reshape(-1, 1))[:, 0]
    pred_rupiah = np.maximum(pred_rupiah, 0)  # tidak boleh negatif

    forecast_trend, forecast_percentage = _derive_trend(pred_rupiah)

    return {
        "forecast_trend":       forecast_trend,
        "forecast_percentage":  forecast_percentage,
        "predictions": [
            {
                "hari_ke":                  i + 1,
                "prediksi_cashflow":        round(float(pred_rupiah[i]), 0),
                "prediksi_cashflow_format": f"Rp {pred_rupiah[i]:,.0f}",
            }
            for i in range(HORIZON)
        ],
        "total_7_hari":     round(float(pred_rupiah.sum()), 0),
        "rata_rata_harian": round(float(pred_rupiah.mean()), 0),
    }