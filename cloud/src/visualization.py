import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


sns.set_theme(style="whitegrid", context="talk")


def _ensure_output_dir(output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def plot_vm_type_distribution(
    labels_df: pd.DataFrame,
    output_dir: str = "./outputs/figures",
    filename: str = "vm_type_distribution.png",
) -> str:
    out_dir = _ensure_output_dir(output_dir)
    counts = labels_df["vm_type"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#E63946", "#457B9D", "#2A9D8F"]
    bars = ax.bar(counts.index, counts.values, color=colors[: len(counts)], edgecolor="black")
    ax.set_title("VM Type Distribution (Google Cluster Workload Trace)", fontweight="bold")
    ax.set_xlabel("VM Type")
    ax.set_ylabel("Number of Tasks")
    for bar, val in zip(bars, counts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{val:,}",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
        )
    total = counts.sum()
    for bar, val in zip(bars, counts.values):
        pct = 100.0 * val / total
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() / 2,
            f"{pct:.1f}%",
            ha="center",
            va="center",
            fontsize=12,
            color="white",
            fontweight="bold",
        )
    ax.tick_params(axis="x", rotation=15)
    plt.tight_layout()
    out_path = os.path.join(out_dir, filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_cpu_vs_memory_scatter(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    output_dir: str = "./outputs/figures",
    filename: str = "cpu_vs_memory_scatter.png",
    max_points: int = 3000,
) -> str:
    out_dir = _ensure_output_dir(output_dir)
    merged = features_df.merge(
        labels_df[["job_id", "task_index", "vm_type"]],
        on=["job_id", "task_index"],
        how="inner",
    )
    if len(merged) > max_points:
        merged = merged.sample(n=max_points, random_state=42)
    fig, ax = plt.subplots(figsize=(9, 7))
    palette = {"cpu_intensive": "#E63946", "memory_intensive": "#457B9D", "balanced": "#2A9D8F"}
    for vtype in ["cpu_intensive", "memory_intensive", "balanced"]:
        sub = merged[merged["vm_type"] == vtype]
        ax.scatter(
            sub["cpu_mean"],
            sub["mem_mean"],
            s=40,
            alpha=0.65,
            label=vtype,
            color=palette.get(vtype, "#888"),
            edgecolors="white",
            linewidth=0.6,
        )
    lim = max(merged["cpu_mean"].max(), merged["mem_mean"].max()) * 1.05
    ax.plot([0, lim], [0, lim], "k--", alpha=0.4, linewidth=1, label="CPU = Memory")
    ax.set_title("Mean CPU Utilization vs Mean Memory Utilization", fontweight="bold")
    ax.set_xlabel("Mean CPU rate (5-min window)")
    ax.set_ylabel("Mean Canonical Memory Usage (5-min window)")
    ax.legend(title="VM Type", loc="best")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    plt.tight_layout()
    out_path = os.path.join(out_dir, filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_confusion_matrix(
    metrics: Dict[str, Any],
    output_dir: str = "./outputs/figures",
    filename: str = "confusion_matrix.png",
) -> str:
    out_dir = _ensure_output_dir(output_dir)
    labels = metrics["labels"]
    cm = metrics["confusion_matrix"]
    fig, ax = plt.subplots(figsize=(7, 6))
    cm_pct = cm.astype("float") / (cm.sum(axis=1, keepdims=True) + 1e-9) * 100
    sns.heatmap(
        cm_pct,
        annot=True,
        fmt=".1f",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
        cbar_kws={"label": "Row % (True class)"},
        ax=ax,
    )
    n_rows, n_cols = cm.shape
    for i in range(n_rows):
        for j in range(n_cols):
            count = int(cm[i, j])
            pct = cm_pct[i, j]
            color = "white" if pct > 40 else "black"
            ax.text(
                j + 0.5,
                i + 0.5,
                f"{pct:.1f}%\n(n={count})",
                ha="center",
                va="center",
                color=color,
                fontsize=9,
            )
    ax.set_title(f"Confusion Matrix [{metrics['subset'].upper()}]", fontweight="bold")
    ax.set_xlabel("Predicted VM Type")
    ax.set_ylabel("True VM Type")
    ax.tick_params(axis="x", rotation=15)
    ax.tick_params(axis="y", rotation=0)
    plt.tight_layout()
    out_path = os.path.join(out_dir, filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_feature_importance_like(
    feature_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    output_dir: str = "./outputs/figures",
    filename: str = "feature_means_by_vm_type.png",
) -> str:
    out_dir = _ensure_output_dir(output_dir)
    merged = feature_df.merge(
        labels_df[["job_id", "task_index", "vm_type"]],
        on=["job_id", "task_index"],
        how="inner",
    )
    feature_cols = [
        "cpu_request",
        "memory_request",
        "cpu_mean",
        "mem_mean",
        "cpu_std",
        "mem_std",
        "cpu_to_mem_ratio",
    ]
    available = [c for c in feature_cols if c in merged.columns]
    grouped = merged.groupby("vm_type")[available].mean()
    grouped_norm = grouped.div(grouped.max(axis=0), axis=1).fillna(0.0)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    grouped_norm.T.plot(
        kind="bar",
        ax=ax,
        color=["#E63946", "#2A9D8F", "#457B9D"],
        edgecolor="black",
    )
    ax.set_title("Normalized Mean Features by VM Type", fontweight="bold")
    ax.set_xlabel("Feature")
    ax.set_ylabel("Normalized Mean Value (row-normalized)")
    ax.legend(title="VM Type", loc="upper right")
    ax.tick_params(axis="x", rotation=25)
    plt.tight_layout()
    out_path = os.path.join(out_dir, filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_train_test_comparison(
    train_metrics: Dict[str, Any],
    test_metrics: Dict[str, Any],
    output_dir: str = "./outputs/figures",
    filename: str = "train_test_metrics_comparison.png",
) -> str:
    out_dir = _ensure_output_dir(output_dir)
    names = ["Accuracy", "Bal. Acc.", "Macro F1", "Weighted F1", "Kappa"]
    keys = ["accuracy", "balanced_accuracy", "macro_f1", "weighted_f1", "cohen_kappa"]
    train_vals = [train_metrics[k] * 100 for k in keys]
    test_vals = [test_metrics[k] * 100 for k in keys]
    x = np.arange(len(names))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars1 = ax.bar(x - width / 2, train_vals, width, label="Train", color="#1D3557", edgecolor="black")
    bars2 = ax.bar(x + width / 2, test_vals, width, label="Test", color="#E63946", edgecolor="black")
    ax.set_ylabel("Score (%)")
    ax.set_title("Classification Metrics: Train vs Test", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15)
    ax.set_ylim(0, 110)
    ax.legend(loc="upper right")
    for bars in (bars1, bars2):
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h,
                f"{h:.1f}%",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )
    plt.tight_layout()
    out_path = os.path.join(out_dir, filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_accuracy_summary_bar(
    test_metrics: Dict[str, Any],
    output_dir: str = "./outputs/figures",
    filename: str = "test_accuracy_summary.png",
) -> str:
    out_dir = _ensure_output_dir(output_dir)
    labels_list = list(test_metrics["per_class"].keys())
    per_class_acc = []
    cm = test_metrics["confusion_matrix"]
    for i, _ in enumerate(labels_list):
        row_sum = cm[i].sum()
        diag = cm[i, i] if row_sum > 0 else 0
        per_class_acc.append(100.0 * diag / (row_sum + 1e-9))
    overall = test_metrics["accuracy"] * 100
    bal = test_metrics["balanced_accuracy"] * 100
    all_labels = labels_list + ["Overall Acc.", "Balanced Acc."]
    all_values = per_class_acc + [overall, bal]
    colors = ["#2A9D8F"] * len(labels_list) + ["#1D3557", "#E63946"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(all_labels, all_values, color=colors, edgecolor="black")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("VM Type Classification Accuracy (Test Set)", fontweight="bold")
    ax.set_ylim(0, 110)
    ax.axhline(50, color="gray", linestyle="--", alpha=0.5, linewidth=1)
    ax.tick_params(axis="x", rotation=20)
    for bar, val in zip(bars, all_values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )
    plt.tight_layout()
    out_path = os.path.join(out_dir, filename)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def generate_all_figures(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    train_metrics: Dict[str, Any],
    test_metrics: Dict[str, Any],
    output_dir: str = "./outputs/figures",
) -> Dict[str, str]:
    paths: Dict[str, str] = {}
    print()
    print(">> Generating figures...")
    paths["vm_type_distribution"] = plot_vm_type_distribution(
        labels_df, output_dir=output_dir
    )
    paths["cpu_vs_memory_scatter"] = plot_cpu_vs_memory_scatter(
        features_df, labels_df, output_dir=output_dir
    )
    paths["feature_means"] = plot_feature_importance_like(
        features_df, labels_df, output_dir=output_dir
    )
    paths["confusion_matrix_test"] = plot_confusion_matrix(
        test_metrics, output_dir=output_dir, filename="confusion_matrix_test.png"
    )
    paths["confusion_matrix_train"] = plot_confusion_matrix(
        train_metrics, output_dir=output_dir, filename="confusion_matrix_train.png"
    )
    paths["train_test_compare"] = plot_train_test_comparison(
        train_metrics, test_metrics, output_dir=output_dir
    )
    paths["accuracy_summary"] = plot_accuracy_summary_bar(
        test_metrics, output_dir=output_dir
    )
    for name, p in paths.items():
        print(f"   [OK] {name:<25} -> {p}")
    return paths
