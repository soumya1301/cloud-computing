from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler


EVENT_SUBMIT = 0
EVENT_SCHEDULE = 1
EVENT_FINISH = 4

VM_TYPE_CPU_INTENSIVE = "cpu_intensive"
VM_TYPE_MEMORY_INTENSIVE = "memory_intensive"
VM_TYPE_BALANCED = "balanced"


class Preprocessor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pp_cfg = config["preprocessing"]
        self.data_cfg = config["data"]
        self.split_cfg = config["split"]

        self.time_interval_us = (
            self.data_cfg["time_interval_seconds"] * 1_000_000
        )
        self.history_window_us = (
            self.data_cfg["history_window_seconds"] * 1_000_000
        )
        self.threshold = self.pp_cfg["vm_type_threshold"]
        self.epsilon = self.pp_cfg["epsilon"]

        self._scalers: Dict[str, Any] = {}

    def clean_missing(
        self, task_usage: pd.DataFrame, task_events: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        usage_req_cols = self.config["tables"]["task_usage"]["required_columns"]
        task_usage = task_usage.dropna(subset=usage_req_cols)

        events_req_cols = self.config["tables"]["task_events"]["required_columns"]
        task_events = task_events.dropna(subset=events_req_cols)

        max_pct = self.pp_cfg["max_missing_pct_allowed"]
        for col in usage_req_cols:
            miss_pct = task_usage[col].isna().mean() * 100
            if miss_pct > max_pct:
                print(
                    f"[WARN] task_usage.{col} has {miss_pct:.2f}% missing values"
                )

        return task_usage, task_events

    def build_task_arrivals(self, task_events: pd.DataFrame) -> pd.DataFrame:
        submit = task_events[task_events["event_type"] == EVENT_SUBMIT].copy()
        submit = submit.drop_duplicates(
            subset=["job_id", "task_index"], keep="first"
        )
        submit = submit.rename(columns={"timestamp": "submit_time"})

        schedule = task_events[task_events["event_type"] == EVENT_SCHEDULE].copy()
        schedule = schedule.drop_duplicates(
            subset=["job_id", "task_index"], keep="first"
        )
        schedule = schedule[
            ["job_id", "task_index", "timestamp", "machine_id"]
        ].rename(columns={"timestamp": "schedule_time", "machine_id": "sched_machine_id"})

        finish = task_events[task_events["event_type"] == EVENT_FINISH].copy()
        finish = finish.drop_duplicates(
            subset=["job_id", "task_index"], keep="last"
        )
        finish = finish[["job_id", "task_index", "timestamp"]].rename(
            columns={"timestamp": "finish_time"}
        )

        arrivals = submit.merge(
            schedule, on=["job_id", "task_index"], how="left"
        )
        arrivals = arrivals.merge(
            finish, on=["job_id", "task_index"], how="left"
        )
        return arrivals

    def extract_history_window(
        self,
        task_usage: pd.DataFrame,
        arrivals: pd.DataFrame,
    ) -> pd.DataFrame:
        usage_cols = [
            "job_id",
            "task_index",
            "start_time",
            "end_time",
            "cpu_rate",
            "canonical_memory_usage",
            "cpu_rate_sample",
            "disk_io_time",
            "machine_id",
        ]
        usage_slim = task_usage[usage_cols].copy()
        usage_slim = usage_slim.dropna(
            subset=["cpu_rate", "canonical_memory_usage"]
        )

        merged = usage_slim.merge(
            arrivals[
                [
                    "job_id",
                    "task_index",
                    "schedule_time",
                    "submit_time",
                    "cpu_request",
                    "memory_request",
                    "scheduling_class",
                    "priority",
                ]
            ],
            on=["job_id", "task_index"],
            how="inner",
        )

        if "schedule_time" in merged.columns:
            mask_sched = merged["schedule_time"].notna()
            merged.loc[mask_sched, "t_zero"] = merged.loc[mask_sched, "schedule_time"]
            merged.loc[~mask_sched, "t_zero"] = merged.loc[~mask_sched, "submit_time"]
        else:
            merged["t_zero"] = merged["submit_time"]

        merged["offset_from_start_us"] = merged["start_time"] - merged["t_zero"]
        in_window = merged[
            (merged["offset_from_start_us"] >= 0)
            & (merged["offset_from_start_us"] <= self.history_window_us)
        ]
        return in_window

    def build_task_records(
        self, history_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        group_cols = ["job_id", "task_index"]

        agg_spec = {
            "cpu_rate": ["mean", "std", "min", "max", "count"],
            "canonical_memory_usage": ["mean", "std", "min", "max"],
            "cpu_rate_sample": ["mean", "std"],
            "disk_io_time": ["mean"],
            "t_zero": ["first"],
            "cpu_request": ["first"],
            "memory_request": ["first"],
            "scheduling_class": ["first"],
            "priority": ["first"],
            "submit_time": ["first"],
            "schedule_time": ["first"],
        }

        grouped = history_df.groupby(group_cols).agg(agg_spec)
        grouped.columns = ["_".join(col).strip() for col in grouped.columns.values]
        grouped = grouped.reset_index()

        grouped = grouped.rename(
            columns={
                "t_zero_first": "t_zero",
                "cpu_request_first": "cpu_request",
                "memory_request_first": "memory_request",
                "scheduling_class_first": "scheduling_class",
                "priority_first": "priority",
                "submit_time_first": "submit_time",
                "schedule_time_first": "schedule_time",
                "cpu_rate_count": "usage_records_in_window",
            }
        )

        grouped["cpu_mean"] = grouped["cpu_rate_mean"].fillna(0.0)
        grouped["mem_mean"] = grouped["canonical_memory_usage_mean"].fillna(0.0)
        grouped["cpu_std"] = grouped["cpu_rate_std"].fillna(0.0)
        grouped["mem_std"] = grouped["canonical_memory_usage_std"].fillna(0.0)
        grouped["cpu_min"] = grouped["cpu_rate_min"].fillna(0.0)
        grouped["mem_min"] = grouped["canonical_memory_usage_min"].fillna(0.0)
        grouped["cpu_max"] = grouped["cpu_rate_max"].fillna(0.0)
        grouped["mem_max"] = grouped["canonical_memory_usage_max"].fillna(0.0)
        grouped["cpu_sample_mean"] = grouped["cpu_rate_sample_mean"].fillna(0.0)
        grouped["disk_io_mean"] = grouped["disk_io_time_mean"].fillna(0.0)

        grouped["cpu_to_mem_ratio"] = grouped["cpu_mean"] / (
            grouped["mem_mean"] + self.epsilon
        )

        def classify_vm_type(row: pd.Series) -> str:
            r = row["cpu_to_mem_ratio"]
            if r >= self.threshold:
                return VM_TYPE_CPU_INTENSIVE
            elif r <= 1.0 / self.threshold:
                return VM_TYPE_MEMORY_INTENSIVE
            else:
                return VM_TYPE_BALANCED

        grouped["vm_type"] = grouped.apply(classify_vm_type, axis=1)

        feature_cols = [
            "cpu_request",
            "memory_request",
            "scheduling_class",
            "priority",
            "cpu_mean",
            "cpu_std",
            "cpu_min",
            "cpu_max",
            "mem_mean",
            "mem_std",
            "mem_min",
            "mem_max",
            "cpu_sample_mean",
            "disk_io_mean",
            "cpu_to_mem_ratio",
            "usage_records_in_window",
        ]

        feature_df = grouped[group_cols + feature_cols].copy()
        label_df = grouped[group_cols + ["vm_type", "t_zero"]].copy()

        return feature_df, label_df

    def build_history_sequences(
        self,
        history_df: pd.DataFrame,
        seq_len: int = 6,
    ) -> Dict[Tuple[int, int], np.ndarray]:
        sequences: Dict[Tuple[int, int], np.ndarray] = {}
        feature_fields = [
            "cpu_rate",
            "canonical_memory_usage",
            "cpu_rate_sample",
            "disk_io_time",
        ]

        for (jid, tid), grp in history_df.groupby(["job_id", "task_index"]):
            grp = grp.sort_values("offset_from_start_us")
            vals = grp[feature_fields].fillna(0.0).values
            n = len(vals)
            if n >= seq_len:
                seq = vals[:seq_len]
            else:
                pad = np.zeros((seq_len - n, len(feature_fields)))
                seq = np.vstack([vals, pad])
            sequences[(int(jid), int(tid))] = seq
        return sequences

    def scale_features(
        self,
        feature_df: pd.DataFrame,
        fit: bool = True,
    ) -> pd.DataFrame:
        if not self.pp_cfg["apply_feature_scaling"]:
            return feature_df.copy()
        method = self.pp_cfg["scaling_method"]
        feature_cols = [
            c for c in feature_df.columns
            if c not in ("job_id", "task_index")
        ]

        if fit:
            if method == "minmax":
                scaler = MinMaxScaler(feature_range=(0, 1), clip=True)
            else:
                scaler = StandardScaler()
            scaled_vals = scaler.fit_transform(feature_df[feature_cols].values)
            self._scalers["features"] = scaler
        else:
            scaler = self._scalers.get("features")
            if scaler is None:
                raise ValueError("Scaler has not been fitted yet.")
            scaled_vals = scaler.transform(feature_df[feature_cols].values)

        out = feature_df[["job_id", "task_index"]].copy()
        for i, col in enumerate(feature_cols):
            out[col] = scaled_vals[:, i]
        return out

    def temporal_train_test_split(
        self,
        feature_df: pd.DataFrame,
        label_df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        merged = feature_df.merge(
            label_df[["job_id", "task_index", "t_zero"]],
            on=["job_id", "task_index"],
            how="inner",
        )
        merged = merged.sort_values("t_zero").reset_index(drop=True)

        n = len(merged)
        train_ratio = self.split_cfg["train_ratio"]
        split_idx = int(n * train_ratio)

        train = merged.iloc[:split_idx]
        test = merged.iloc[split_idx:]

        train_feat = train.drop(columns=["t_zero"])
        test_feat = test.drop(columns=["t_zero"])

        train_label = label_df.merge(
            train[["job_id", "task_index"]],
            on=["job_id", "task_index"],
            how="inner",
        )
        test_label = label_df.merge(
            test[["job_id", "task_index"]],
            on=["job_id", "task_index"],
            how="inner",
        )
        return train_feat, test_feat, train_label, test_label

    def preprocess(
        self,
        task_usage: pd.DataFrame,
        task_events: pd.DataFrame,
        job_events: Optional[pd.DataFrame] = None,
        machine_events: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        print("[1/6] Cleaning missing values...")
        task_usage_c, task_events_c = self.clean_missing(task_usage, task_events)
        print(f"       task_usage  rows kept: {len(task_usage_c):,}")
        print(f"       task_events rows kept: {len(task_events_c):,}")

        print("[2/6] Building task arrival records (submit/schedule/finish)...")
        arrivals = self.build_task_arrivals(task_events_c)
        print(f"       unique tasks with arrivals: {len(arrivals):,}")

        print("[3/6] Extracting 5-minute post-arrival workload history...")
        history = self.extract_history_window(task_usage_c, arrivals)
        print(f"       rows within observation window: {len(history):,}")

        print("[4/6] Constructing per-task feature and label records...")
        feature_df, label_df = self.build_task_records(history)
        print(f"       unique task records constructed: {len(feature_df):,}")
        type_counts = label_df["vm_type"].value_counts().to_dict()
        for t, c in type_counts.items():
            print(f"         {t}: {c}")

        print("[5/6] Building 5-minute time-step sequences...")
        sequences = self.build_history_sequences(history)
        print(f"       sequences generated: {len(sequences):,}")

        print("[6/6] Scaling features and splitting train/test...")
        feature_df_scaled = self.scale_features(feature_df, fit=True)
        train_feat, test_feat, train_lbl, test_lbl = (
            self.temporal_train_test_split(feature_df_scaled, label_df)
        )
        print(f"       train tasks: {len(train_feat):,}  |  test tasks: {len(test_feat):,}")

        return {
            "features": feature_df,
            "features_scaled": feature_df_scaled,
            "labels": label_df,
            "sequences": sequences,
            "train_features": train_feat,
            "test_features": test_feat,
            "train_labels": train_lbl,
            "test_labels": test_lbl,
            "arrivals": arrivals,
            "history_window_rows": history,
        }
