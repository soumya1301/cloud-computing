import os
import glob
import gzip
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from tqdm import tqdm


class GoogleClusterDataLoader:
    def __init__(self, data_path: str, config: Dict[str, Any]):
        self.data_path = os.path.abspath(data_path)
        self.config = config
        self.tables_config = config["tables"]
        self._dfs: Dict[str, pd.DataFrame] = {}

    def _list_part_files(self, table_name: str) -> List[str]:
        table_dir = os.path.join(
            self.data_path, self.tables_config[table_name]["dir"]
        )
        pattern = os.path.join(table_dir, "part-*.csv.gz")
        files = sorted(glob.glob(pattern))
        return files

    def _read_table(self, table_name: str, max_parts: Optional[int] = None) -> pd.DataFrame:
        col_names = self.tables_config[table_name]["columns"]
        files = self._list_part_files(table_name)
        if max_parts is not None:
            files = files[:max_parts]
        if not files:
            return pd.DataFrame(columns=col_names)

        frames = []
        for fpath in tqdm(
            files, desc=f"Loading {table_name}", unit="part", leave=False
        ):
            try:
                with gzip.open(fpath, "rt") as f:
                    df = pd.read_csv(
                        f,
                        header=None,
                        names=col_names,
                        dtype={
                            "job_id": "Int64",
                            "task_index": "Int64",
                            "machine_id": "Int64",
                            "event_type": "Int32",
                            "scheduling_class": "Int32",
                            "priority": "Int32",
                        },
                        on_bad_lines="skip",
                    )
                frames.append(df)
            except Exception as e:
                print(f"Warning: failed to parse {fpath}: {e}")
        if not frames:
            return pd.DataFrame(columns=col_names)
        result = pd.concat(frames, ignore_index=True)
        return result

    def load_all(
        self,
        max_parts_per_table: Optional[int] = None,
        tables: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        load_tables = tables or [
            "task_usage",
            "task_events",
            "job_events",
            "machine_events",
        ]
        for name in load_tables:
            if name not in self.tables_config:
                continue
            self._dfs[name] = self._read_table(name, max_parts=max_parts_per_table)
            print(f"  Loaded {name}: {len(self._dfs[name]):,} rows")
        return self._dfs

    def load_task_usage(self, max_parts: Optional[int] = None) -> pd.DataFrame:
        self._dfs["task_usage"] = self._read_table("task_usage", max_parts=max_parts)
        return self._dfs["task_usage"]

    def load_task_events(self, max_parts: Optional[int] = None) -> pd.DataFrame:
        self._dfs["task_events"] = self._read_table("task_events", max_parts=max_parts)
        return self._dfs["task_events"]

    def load_job_events(self, max_parts: Optional[int] = None) -> pd.DataFrame:
        self._dfs["job_events"] = self._read_table("job_events", max_parts=max_parts)
        return self._dfs["job_events"]

    def load_machine_events(self, max_parts: Optional[int] = None) -> pd.DataFrame:
        self._dfs["machine_events"] = self._read_table("machine_events", max_parts=max_parts)
        return self._dfs["machine_events"]

    @property
    def task_usage(self) -> pd.DataFrame:
        return self._dfs.get("task_usage", pd.DataFrame())

    @property
    def task_events(self) -> pd.DataFrame:
        return self._dfs.get("task_events", pd.DataFrame())

    @property
    def job_events(self) -> pd.DataFrame:
        return self._dfs.get("job_events", pd.DataFrame())

    @property
    def machine_events(self) -> pd.DataFrame:
        return self._dfs.get("machine_events", pd.DataFrame())
