import os
import sys
from typing import Any, Dict, List, Tuple


REQUIRED_TABLE_DIRS = [
    "task_usage",
    "task_events",
    "job_events",
    "machine_events",
]


class DatasetValidator:
    def __init__(self, data_path: str, config: Dict[str, Any]):
        self.data_path = os.path.abspath(data_path)
        self.config = config
        self.trace_version = config["data"]["trace_version"]

    def validate(self, verbose: bool = True) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        warnings: List[str] = []

        if verbose:
            print("=" * 70)
            print(f"Validating Google Cluster Workload Trace dataset")
            print(f"  Expected version: {self.trace_version}")
            print(f"  Data path: {self.data_path}")
            print("=" * 70)

        if not os.path.exists(self.data_path):
            errors.append(
                f"[ERROR] Data directory does not exist:\n"
                f"        {self.data_path}\n"
                f"\n"
                f"Please download the Google Cluster workload trace dataset and place\n"
                f"the files inside the directory above.\n"
                f"\n"
                f"Download instructions:\n"
                f"  1. Join the mailing list: "
                f"https://groups.google.com/forum/#!forum/googleclusterdata-discuss\n"
                f"  2. Install gcloud CLI: "
                f"https://docs.cloud.google.com/sdk/docs/install-sdk\n"
                f"  3. Authenticate: gcloud auth login\n"
                f"  4. Download into the raw directory:\n"
                f"     gcloud storage cp -r gs://clusterdata-2011-2/* "
                f"{self.data_path}/\n"
                f"\n"
                f"Official source: https://github.com/google/cluster-data\n"
                f"Dataset README:  ./data/google_cluster/README.md\n"
                f"\n"
                f"For testing only (not experimental results), use --sample_mode."
            )
            if verbose:
                print(errors[-1])
            return False, errors

        if not os.path.isdir(self.data_path):
            errors.append(
                f"[ERROR] Path exists but is not a directory: {self.data_path}"
            )

        for table_dir in REQUIRED_TABLE_DIRS:
            full_path = os.path.join(self.data_path, table_dir)
            if not os.path.isdir(full_path):
                errors.append(
                    f"[ERROR] Missing required table directory: {full_path}\n"
                    f"        Expected subdirectory '{table_dir}/' under the raw path.\n"
                    f"        Each directory should contain one or more "
                    f"part-*.csv.gz files."
                )
            else:
                gz_files = [
                    f
                    for f in os.listdir(full_path)
                    if f.endswith(".csv.gz") and f.startswith("part-")
                ]
                if len(gz_files) == 0:
                    errors.append(
                        f"[ERROR] Directory {table_dir}/ exists but contains no "
                        f"part-*.csv.gz files.\n"
                        f"        Please download the corresponding part files "
                        f"from gs://{self.trace_version}/{table_dir}/ ."
                    )
                elif verbose:
                    print(f"  [OK]   {table_dir}/ : {len(gz_files)} part file(s)")

        has_any_gz = False
        for table_dir in REQUIRED_TABLE_DIRS:
            full_path = os.path.join(self.data_path, table_dir)
            if os.path.isdir(full_path):
                gz_files = [
                    f
                    for f in os.listdir(full_path)
                    if f.endswith(".csv.gz")
                ]
                if len(gz_files) > 0:
                    has_any_gz = True
                    break

        attr_path = os.path.join(self.data_path, "machine_attributes")
        if not os.path.isdir(attr_path):
            warnings.append(
                "[WARN]  Optional directory 'machine_attributes/' is missing. "
                "Some advanced features will be unavailable."
            )

        if verbose and warnings:
            for w in warnings:
                print(w)

        if verbose and not errors:
            print()
            print(f"[OK] Dataset validation PASSED.")
            print(f"     Trace version   : {self.trace_version}")
            print(f"     Official source : https://github.com/google/cluster-data")
            print("=" * 70)
        elif verbose and errors:
            print()
            print("[FAIL] Dataset validation FAILED.")
            print("=" * 70)
            print()
            print("Please refer to ./data/google_cluster/README.md for full setup "
                  "instructions.")
            print("If you only want to test the code pipeline (NOT for paper "
                  "experimental results),")
            print("run with: python main.py --sample_mode")

        return (len(errors) == 0), errors

    def print_error_report(self, errors: List[str]) -> None:
        print("\n" + "!" * 70)
        print("  DATASET REQUIRED — Google Cluster Workload Trace")
        print("!" * 70)
        for err in errors:
            print()
            print(err)
        print("!" * 70 + "\n")
