from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    cohen_kappa_score,
)


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    labels: List[str],
    subset_name: str = "test",
) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    results["subset"] = subset_name
    results["num_samples"] = int(len(y_true))

    results["accuracy"] = float(accuracy_score(y_true, y_pred))
    results["balanced_accuracy"] = float(
        balanced_accuracy_score(y_true, y_pred)
    )
    results["macro_f1"] = float(
        f1_score(y_true, y_pred, average="macro", zero_division=0)
    )
    results["weighted_f1"] = float(
        f1_score(y_true, y_pred, average="weighted", zero_division=0)
    )
    results["macro_precision"] = float(
        precision_score(y_true, y_pred, average="macro", zero_division=0)
    )
    results["weighted_precision"] = float(
        precision_score(y_true, y_pred, average="weighted", zero_division=0)
    )
    results["macro_recall"] = float(
        recall_score(y_true, y_pred, average="macro", zero_division=0)
    )
    results["weighted_recall"] = float(
        recall_score(y_true, y_pred, average="weighted", zero_division=0)
    )
    results["cohen_kappa"] = float(cohen_kappa_score(y_true, y_pred))

    cm = confusion_matrix(y_true, y_pred, labels=labels)
    results["confusion_matrix"] = cm
    results["labels"] = list(labels)

    report_dict = classification_report(
        y_true,
        y_pred,
        labels=labels,
        target_names=labels,
        zero_division=0,
        output_dict=True,
    )
    results["per_class"] = {
        label: {
            k: float(v)
            for k, v in report_dict[label].items()
            if k in ("precision", "recall", "f1-score", "support")
        }
        for label in labels
    }
    return results


def print_metrics_report(
    metrics: Dict[str, Any],
    title: str = "Classification Metrics",
) -> None:
    print()
    print("=" * 70)
    print(f"  {title}  [{metrics['subset']} / N={metrics['num_samples']}]")
    print("=" * 70)
    print(f"  Accuracy            : {metrics['accuracy']:.4f}   "
          f"({metrics['accuracy']*100:.2f}%)")
    print(f"  Balanced Accuracy   : {metrics['balanced_accuracy']:.4f}   "
          f"({metrics['balanced_accuracy']*100:.2f}%)")
    print(f"  Cohen's Kappa       : {metrics['cohen_kappa']:.4f}")
    print(f"  Macro F1            : {metrics['macro_f1']:.4f}")
    print(f"  Weighted F1         : {metrics['weighted_f1']:.4f}")
    print(f"  Macro Precision     : {metrics['macro_precision']:.4f}")
    print(f"  Macro Recall        : {metrics['macro_recall']:.4f}")
    print("-" * 70)
    print("  Per-class metrics:")
    print(f"  {'Class':<22} {'Prec':>7} {'Rec':>7} {'F1':>7} {'Support':>8}")
    for label, vals in metrics["per_class"].items():
        print(f"  {label:<22} {vals['precision']:7.3f} "
              f"{vals['recall']:7.3f} {vals['f1-score']:7.3f} "
              f"{int(vals['support']):>8}")
    print("-" * 70)
    print("  Confusion Matrix (rows=true, cols=pred):")
    labels = metrics["labels"]
    cm = metrics["confusion_matrix"]
    header = "  " + "".join(f"{l[:6]:>8}" for l in labels)
    print(header)
    for i, label in enumerate(labels):
        row = "".join(f"{v:>8}" for v in cm[i])
        print(f"  {label[:6]:<6}{row}")
    print("=" * 70)
