import numpy as np
from scipy.signal import butter, sosfiltfilt


def bandpass_filter_ecg(signal: np.ndarray, fs: int, lowcut: float = 0.5, highcut: float = 40.0, order: int = 4) -> np.ndarray:
    nyquist = fs / 2
    sos = butter(order, [lowcut / nyquist, highcut / nyquist], btype="bandpass", output="sos")
    return sosfiltfilt(sos, signal)