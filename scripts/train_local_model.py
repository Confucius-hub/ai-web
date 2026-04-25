"""
# Своя модель — описание процесса обучения

Простой классификатор намерений пользовательских сообщений:
  TfidfVectorizer (character n-grams 2-4) + LogisticRegression (liblinear).

Классы:
  - greeting     (приветствие)
  - question     (вопрос / просьба пояснить)
  - complaint    (жалоба / проблема)
  - request      (конкретная просьба действия)
  - thanks       (благодарность)

Датасет — маленький synthetic-набор (~60 примеров на класс), этого достаточно
для демонстрации и уверенной работы классификатора на коротких фразах.

После обучения пайплайн экспортируется в ONNX через skl2onnx; в проде
используется onnxruntime (см. app/ml/local_onnx.py) — без sklearn в runtime-образе,
что ускоряет cold-start и уменьшает размер образа.

Запуск внутри контейнера api:
    docker compose exec api_a python scripts/train_local_model.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import StringTensorType
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

DATA: list[tuple[str, str]] = [
    # --- greeting ---
    ("hi", "greeting"), ("hello", "greeting"), ("hey there", "greeting"),
    ("good morning", "greeting"), ("good evening", "greeting"),
    ("howdy", "greeting"), ("greetings", "greeting"), ("hi team", "greeting"),
    ("hey assistant", "greeting"), ("hello bot", "greeting"),
    ("hey!", "greeting"), ("hi hi", "greeting"),
    # --- question ---
    ("what is tf-idf", "question"),
    ("how does attention work", "question"),
    ("can you explain backpropagation", "question"),
    ("what's the difference between sync and async", "question"),
    ("why do we need docker", "question"),
    ("how to use fastapi with celery", "question"),
    ("what is a transformer", "question"),
    ("how does redis pub sub work", "question"),
    ("explain pagination please", "question"),
    ("what's the role of alembic", "question"),
    ("what is onnx", "question"),
    ("how to write a pydantic validator", "question"),
    # --- complaint ---
    ("i can't log in to my account", "complaint"),
    ("the page is broken", "complaint"),
    ("nothing works", "complaint"),
    ("this is terrible", "complaint"),
    ("the server keeps crashing", "complaint"),
    ("i'm getting a 500 error", "complaint"),
    ("it's very slow", "complaint"),
    ("the model gives wrong answers", "complaint"),
    ("i lost my data", "complaint"),
    ("your api is not responding", "complaint"),
    ("the latency is unacceptable", "complaint"),
    ("frustrating experience", "complaint"),
    # --- request ---
    ("please summarize this article", "request"),
    ("translate this text to english", "request"),
    ("generate a python script for me", "request"),
    ("write a sql query to find duplicates", "request"),
    ("give me 3 ideas for a thesis", "request"),
    ("draft an email to my supervisor", "request"),
    ("create a unit test for this function", "request"),
    ("review my code", "request"),
    ("make a plan for the week", "request"),
    ("build a json schema for this object", "request"),
    ("refactor this snippet", "request"),
    ("convert this to typescript", "request"),
    # --- thanks ---
    ("thanks", "thanks"), ("thank you", "thanks"),
    ("thanks a lot", "thanks"), ("appreciate it", "thanks"),
    ("many thanks", "thanks"), ("thx", "thanks"),
    ("ty", "thanks"), ("cheers", "thanks"),
    ("thank you very much", "thanks"),
    ("that was perfect thanks", "thanks"),
    ("wonderful, thanks", "thanks"),
    ("great job thank you", "thanks"),
]


def train_and_export(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    texts = [x[0] for x in DATA]
    labels = [x[1] for x in DATA]
    classes = sorted(set(labels))
    label_to_idx = {c: i for i, c in enumerate(classes)}
    y = np.array([label_to_idx[l] for l in labels])

    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 4),
                    min_df=1,
                    lowercase=True,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    solver="liblinear",
                    max_iter=1000,
                    C=2.0,
                ),
            ),
        ]
    )

    pipeline.fit(texts, y)

    # Sanity check
    acc = pipeline.score(texts, y)
    print(f"[train] training accuracy = {acc:.3f}")
    for sample in ["hi!", "how do i train a model", "i can't sign in",
                   "please write a unit test", "thanks so much"]:
        pred = classes[int(pipeline.predict([sample])[0])]
        print(f"  '{sample}' -> {pred}")

    # Export to ONNX
    initial_types = [("input", StringTensorType([None, 1]))]
    onnx_model = convert_sklearn(
        pipeline,
        initial_types=initial_types,
        target_opset=15,
        options={id(pipeline): {"zipmap": False}},
    )

    model_path = out_dir / "intent_classifier.onnx"
    with open(model_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    print(f"[export] wrote {model_path} ({model_path.stat().st_size / 1024:.1f} KB)")

    labels_path = out_dir / "labels.json"
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(classes, f, ensure_ascii=False, indent=2)
    print(f"[export] wrote {labels_path}  labels={classes}")


if __name__ == "__main__":
    # In container: /app/models/
    out = Path("/app/models")
    if not out.parent.exists():
        # Local run
        out = Path(__file__).resolve().parent.parent / "app" / "models"
    train_and_export(out)
