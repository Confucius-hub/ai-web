"""
# Своя модель
# Оптимизация инференса
Локальный классификатор намерений пользователя (intent classification).

Пайплайн обучения (см. scripts/train_local_model.py):
    TfidfVectorizer + LogisticRegression на synthetic-датасете,
    затем экспорт всего пайплайна в ONNX через skl2onnx.

Инференс здесь — через onnxruntime (C++ runtime, без sklearn в prod-контейнере),
что соответствует паттерну ONNX из лекции 1.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

log = logging.getLogger(__name__)


class LocalIntentClassifier:
    def __init__(self, model_path: str, labels_path: str) -> None:
        p_model = Path(model_path)
        p_labels = Path(labels_path)
        if not p_model.exists():
            raise FileNotFoundError(f"ONNX model not found: {model_path}")
        if not p_labels.exists():
            raise FileNotFoundError(f"Labels file not found: {labels_path}")

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Управление ресурсами — лимитируем потоки
        sess_options.intra_op_num_threads = 2
        sess_options.inter_op_num_threads = 1

        self._session = ort.InferenceSession(
            str(p_model),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self._session.get_inputs()[0].name

        with open(p_labels, "r", encoding="utf-8") as f:
            self._labels: list[str] = json.load(f)

        log.info(
            "onnx_loaded",
            extra={
                "model": str(model_path),
                "labels": self._labels,
                "input": self._input_name,
            },
        )

    def predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        """
        Возвращает (label, confidence, all_scores).
        """
        # skl2onnx экспортирует пайплайн так, что на вход идёт массив строк.
        x = np.array([text], dtype=object).reshape(1, 1)
        start = time.perf_counter()
        outputs = self._session.run(None, {self._input_name: x})
        duration_ms = (time.perf_counter() - start) * 1000

        # Два выхода: [labels], [probabilities dict/array]
        label = outputs[0][0]
        probs_raw = outputs[1][0]
        if isinstance(probs_raw, dict):
            # skl2onnx иногда возвращает dict {class_idx: prob}
            scores = {self._labels[int(k)]: float(v) for k, v in probs_raw.items()}
        else:
            scores = {self._labels[i]: float(p) for i, p in enumerate(probs_raw)}

        best_label = str(label) if str(label) in scores else max(scores, key=scores.get)
        confidence = scores[best_label]

        log.info(
            "intent_predicted",
            extra={"duration_ms": round(duration_ms, 2), "label": best_label},
        )
        return best_label, confidence, scores
