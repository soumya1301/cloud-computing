import argparse
import os
import sys
from typing import Any, Dict

from src.config import load_config
from src.dataset_validator import DatasetValidator
from src.data_loader import GoogleClusterDataLoader
from src.preprocessing import Preprocessor
from src.sample_mode import generate_sample_dataset
from src.model import VMTypeClassifier
from src.evaluation import compute_metrics, print_metrics_report
from src.visualization import generate_all_figures


DEFAULT_DATA_PATH = "./data/google_cluster/raw/"
DEFAULT_CONFIG_PATH = "./config/config.yaml"
DEFAULT_OUTPUT_DIR = "./outputs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "VM placement optimization using Google Cluster Workload Trace "
            "(clusterdata-2011-2). Implements the preprocessing pipeline, "
            "Autoencoder+SVM classification, evaluation metrics and "
            "figures, as described in Alelyani et al. (2026)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Dataset:\n"
            "  Google Cluster Workload Trace\n"
            "  Version : clusterdata-2011-2\n"
            "  Source  : https://github.com/google/cluster-data\n\n"
            "Examples:\n"
            "  python main.py --validate\n"
            "  python main.py --data_path ./data/google_cluster/raw/\n"
            "  python main.py --sample_mode\n"
            "  python main.py --sample_mode --output_dir ./outputs\n"
        ),
    )
    parser.add_argument(
        "--data_path",
        type=str,
        default=DEFAULT_DATA_PATH,
        help=(
            "Path to the directory containing the raw Google Cluster trace "
            "files (default: %(default)s). Must contain subdirectories "
            "task_usage/, task_events/, job_events/, machine_events/ each "
            "with part-*.csv.gz files."
        ),
    )
    parser.add_argument(
        "--config_path",
        type=str,
        default=DEFAULT_CONFIG_PATH,
        help="Path to YAML configuration file (default: %(default)s).",
    )
    parser.add_argument(
        "--max_parts",
        type=int,
        default=None,
        help=(
            "Maximum number of part files to load per table (useful for "
            "small-scale debugging). Default: load all available parts."
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Only validate dataset presence/structure, then exit.",
    )
    parser.add_argument(
        "--sample_mode",
        action="store_true",
        help=(
            "[TEST MODE ONLY] Generate a small synthetic sample that mimics "
            "the Google trace schema, and run the pipeline on it. "
            "Do NOT use results from this mode for paper experiments."
        ),
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Directory where classification metrics and figures are saved "
            "(default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--no_figures",
        action="store_true",
        help="Skip figure generation (only print metrics).",
    )
    return parser.parse_args()


def print_header() -> None:
    print()
    print("=" * 70)
    print("  VM Placement Optimization — Google Cluster Workload Trace Pipeline")
    print("  Paper : Alelyani, Datta & Hassan (2026), Journal of Cloud Computing")
    print("  DOI   : 10.1186/s13677-026-00851-3")
    print("  Model : Autoencoder (latent features) + SVM classifier (VM type)")
    print("=" * 70)
    print()


def run_pipeline(
    loader: GoogleClusterDataLoader,
    preprocessor: Preprocessor,
    max_parts: Any,
) -> Dict[str, Any]:
    print(">> Loading Google Cluster Workload Trace tables")
    dfs = loader.load_all(max_parts_per_table=max_parts)
    print()
    print(">> Running preprocessing pipeline per paper methodology")
    result = preprocessor.preprocess(
        task_usage=dfs["task_usage"],
        task_events=dfs["task_events"],
        job_events=dfs.get("job_events"),
        machine_events=dfs.get("machine_events"),
    )
    return result


def summarize_results(result: Dict[str, Any]) -> None:
    print()
    print("=" * 70)
    print("  Pipeline Complete — Summary")
    print("=" * 70)
    print(f"  Total unique tasks processed : {len(result['features']):,}")
    print(f"  Feature columns              : "
          f"{[c for c in result['features'].columns if c not in ('job_id','task_index')]}")
    vc = result["labels"]["vm_type"].value_counts()
    print(f"  VM type distribution         : "
          f"{vc.to_dict()}")
    print(f"  Train set size               : {len(result['train_features']):,}")
    print(f"  Test set size                : {len(result['test_features']):,}")
    print(f"  5-min sequences available    : {len(result['sequences']):,}")
    print()
    print("  Dataset: Google Cluster Workload Trace")
    print("  Version: clusterdata-2011-2")
    print("  Source : https://github.com/google/cluster-data")
    print("=" * 70)


def run_training_and_evaluation(
    result: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    print()
    print(">> Training Autoencoder + SVM classifier")
    classifier = VMTypeClassifier(config)
    train_pred, test_pred = classifier.fit_predict(
        train_features=result["train_features"],
        train_labels=result["train_labels"],
        test_features=result["test_features"],
    )

    y_train_true = result["train_labels"]["vm_type"].values
    y_test_true = result["test_labels"]["vm_type"].values
    labels_order = list(classifier.label_encoder.classes_)

    train_metrics = compute_metrics(
        y_train_true, train_pred, labels_order, subset_name="train"
    )
    test_metrics = compute_metrics(
        y_test_true, test_pred, labels_order, subset_name="test"
    )

    print_metrics_report(train_metrics, title="Train Classification Metrics")
    print_metrics_report(test_metrics, title="Test Classification Metrics")

    return {
        "classifier": classifier,
        "train_pred": train_pred,
        "test_pred": test_pred,
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
    }


def save_evaluation_artifacts(
    output_dir: str,
    train_metrics: Dict[str, Any],
    test_metrics: Dict[str, Any],
    sample_mode: bool,
) -> str:
    out_dir = os.path.abspath(output_dir)
    os.makedirs(out_dir, exist_ok=True)
    metrics_path = os.path.join(out_dir, "metrics_summary.txt")
    with open(metrics_path, "w") as f:
        if sample_mode:
            f.write("WARNING: RESULTS FROM SAMPLE MODE (SYNTHETIC DATA)\n")
            f.write("DO NOT USE FOR PAPER EXPERIMENTAL RESULTS\n\n")
        f.write("Dataset: Google Cluster Workload Trace\n")
        f.write("Version: clusterdata-2011-2\n")
        f.write("Source : https://github.com/google/cluster-data\n\n")
        for name, metrics in [("TRAIN", train_metrics), ("TEST", test_metrics)]:
            f.write("=" * 70 + "\n")
            f.write(f"  {name} CLASSIFICATION METRICS\n")
            f.write("=" * 70 + "\n")
            f.write(f"  Num samples         : {metrics['num_samples']}\n")
            f.write(f"  Accuracy            : {metrics['accuracy']:.6f} "
                    f"({metrics['accuracy']*100:.4f}%)\n")
            f.write(f"  Balanced Accuracy   : {metrics['balanced_accuracy']:.6f} "
                    f"({metrics['balanced_accuracy']*100:.4f}%)\n")
            f.write(f"  Cohen's Kappa       : {metrics['cohen_kappa']:.6f}\n")
            f.write(f"  Macro F1            : {metrics['macro_f1']:.6f}\n")
            f.write(f"  Weighted F1         : {metrics['weighted_f1']:.6f}\n")
            f.write(f"  Macro Precision     : {metrics['macro_precision']:.6f}\n")
            f.write(f"  Macro Recall        : {metrics['macro_recall']:.6f}\n")
            f.write("-" * 70 + "\n")
            f.write("  Per-class metrics:\n")
            f.write(f"  {'Class':<22} {'Prec':>7} {'Rec':>7} {'F1':>7} {'Support':>8}\n")
            for label, vals in metrics["per_class"].items():
                f.write(f"  {label:<22} {vals['precision']:7.3f} "
                        f"{vals['recall']:7.3f} {vals['f1-score']:7.3f} "
                        f"{int(vals['support']):>8}\n")
            f.write("-" * 70 + "\n")
            f.write("  Confusion Matrix (rows=true, cols=pred):\n")
            labels = metrics["labels"]
            cm = metrics["confusion_matrix"]
            f.write("  " + "".join(f"{l[:6]:>8}" for l in labels) + "\n")
            for i, label in enumerate(labels):
                row = "".join(f"{v:>8}" for v in cm[i])
                f.write(f"  {label[:6]:<6}{row}\n")
            f.write("\n")
    return metrics_path


def execute_full_flow(
    data_path: str,
    output_dir: str,
    config: Dict[str, Any],
    task_usage, task_events, job_events, machine_events,
    sample_mode: bool,
    no_figures: bool,
    max_parts: Any,
) -> int:
    preprocessor = Preprocessor(config)
    if task_usage is not None and task_events is not None:
        dfs = {
            "task_usage": task_usage,
            "task_events": task_events,
            "job_events": job_events,
            "machine_events": machine_events,
        }
        print(">> Running preprocessing pipeline per paper methodology")
        result = preprocessor.preprocess(
            task_usage=dfs["task_usage"],
            task_events=dfs["task_events"],
            job_events=dfs.get("job_events"),
            machine_events=dfs.get("machine_events"),
        )
    else:
        loader = GoogleClusterDataLoader(data_path, config)
        result = run_pipeline(loader, preprocessor, max_parts)

    summarize_results(result)
    eval_out = run_training_and_evaluation(result, config)
    test_metrics = eval_out["test_metrics"]
    train_metrics = eval_out["train_metrics"]

    metrics_txt_path = save_evaluation_artifacts(
        output_dir, train_metrics, test_metrics, sample_mode
    )
    print(f"\n  Metrics saved to    : {metrics_txt_path}")

    figure_paths = {}
    if not no_figures:
        figures_dir = os.path.join(output_dir, "figures")
        figure_paths = generate_all_figures(
            features_df=result["features"],
            labels_df=result["labels"],
            train_metrics=train_metrics,
            test_metrics=test_metrics,
            output_dir=figures_dir,
        )

    print()
    print("=" * 70)
    print("  FINAL TEST ACCURACY SUMMARY")
    print("=" * 70)
    print(f"  Overall Accuracy       : {test_metrics['accuracy']:.4f} "
          f"({test_metrics['accuracy']*100:.2f}%)")
    print(f"  Balanced Accuracy      : {test_metrics['balanced_accuracy']:.4f} "
          f"({test_metrics['balanced_accuracy']*100:.2f}%)")
    print(f"  Macro F1 Score         : {test_metrics['macro_f1']:.4f}")
    print(f"  Weighted F1 Score      : {test_metrics['weighted_f1']:.4f}")
    print(f"  Cohen's Kappa          : {test_metrics['cohen_kappa']:.4f}")
    for label, vals in test_metrics["per_class"].items():
        print(f"  {label:<22} F1={vals['f1-score']:.3f}  "
              f"Prec={vals['precision']:.3f}  Rec={vals['recall']:.3f}  "
              f"N={int(vals['support'])}")
    if figure_paths:
        print(f"\n  Figures saved under   : {os.path.dirname(list(figure_paths.values())[0])}/")
        for name, p in figure_paths.items():
            print(f"    - {name:<25} {os.path.basename(p)}")
    print()
    if sample_mode:
        print("[NOTE] The above accuracy and graphs were produced in SAMPLE MODE")
        print("       using synthetic data. They are NOT the paper's experimental")
        print("       results. For real results, download the Google cluster")
        print("       dataset as described in ./data/google_cluster/README.md")
    print("=" * 70)
    return 0


def main() -> int:
    args = parse_args()
    print_header()

    config_path = os.path.abspath(args.config_path)
    config = load_config(config_path)
    data_path = os.path.abspath(args.data_path)
    output_dir = os.path.abspath(args.output_dir)
    print(f"Configuration: {config_path}")
    print(f"Data path    : {data_path}")
    print(f"Output dir   : {output_dir}")
    print(f"Trace version: {config['data']['trace_version']}")
    print()

    if args.sample_mode:
        sample_cfg = config.get("sample_mode", {})
        if not sample_cfg:
            sample_cfg = {"num_tasks": 500, "num_machines": 100, "num_intervals": 10}
        task_usage, task_events, job_events, machine_events = (
            generate_sample_dataset(data_path, config)
        )
        print()
        return execute_full_flow(
            data_path=data_path,
            output_dir=output_dir,
            config=config,
            task_usage=task_usage,
            task_events=task_events,
            job_events=job_events,
            machine_events=machine_events,
            sample_mode=True,
            no_figures=args.no_figures,
            max_parts=args.max_parts,
        )

    validator = DatasetValidator(data_path, config)
    ok, errors = validator.validate(verbose=True)
    if args.validate:
        return 0 if ok else 1

    if not ok:
        validator.print_error_report(errors)
        return 1

    return execute_full_flow(
        data_path=data_path,
        output_dir=output_dir,
        config=config,
        task_usage=None,
        task_events=None,
        job_events=None,
        machine_events=None,
        sample_mode=False,
        no_figures=args.no_figures,
        max_parts=args.max_parts,
    )


if __name__ == "__main__":
    sys.exit(main())
