import os
import gzip
import random
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd


USAGE_COLS = [
    "start_time", "end_time", "job_id", "task_index", "machine_id",
    "cpu_rate", "canonical_memory_usage", "assigned_memory_usage",
    "unmapped_page_cache", "total_page_cache", "max_memory_usage",
    "disk_io_time", "local_disk_space_used", "cpu_rate_sample",
    "cpi", "mai", "sample_portality", "agg_type_used_cpu", "agg_type_used_memory",
]

EVENT_COLS = [
    "timestamp", "missing_info", "job_id", "task_index", "machine_id",
    "event_type", "user", "scheduling_class", "priority",
    "cpu_request", "memory_request", "disk_space_request", "machines_restriction",
]

JOB_EVENT_COLS = [
    "timestamp", "missing_info", "job_id", "event_type", "user",
    "scheduling_class", "job_name", "logical_job_name",
]

MACHINE_EVENT_COLS = [
    "timestamp", "machine_id", "event_type", "platform_id",
    "capacity_cpu", "capacity_memory",
]


def _rand_normal_pos(mean: float, std: float, size: int = 1) -> np.ndarray:
    vals = np.random.normal(mean, std, size=size)
    return np.clip(vals, 1e-4, 1.0)


def generate_sample_dataset(
    data_path: str,
    config: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = config["sample_mode"]
    num_tasks = cfg["num_tasks"]
    num_machines = cfg["num_machines"]
    num_intervals = cfg["num_intervals"]
    seed = config["split"]["random_seed"]

    np.random.seed(seed)
    random.seed(seed)

    print("=" * 70)
    print("  TEST MODE — Generating synthetic sample dataset")
    print("  WARNING: Results are NOT from the real Google trace.")
    print("           Do NOT use for paper experimental results.")
    print(f"           num_tasks={num_tasks}, num_machines={num_machines}")
    print("=" * 70)

    base_time_us = config["data"]["trace_start_timestamp"] * 1_000_000
    interval_us = config["data"]["time_interval_seconds"] * 1_000_000
    window_us = config["data"]["history_window_seconds"] * 1_000_000

    machine_ids = np.arange(1, num_machines + 1)
    platform_ids = np.array(["plat_A", "plat_B", "plat_C"])

    machine_events_rows = []
    for mid in machine_ids:
        cpu_cap = float(_rand_normal_pos(1.0, 0.15)[0])
        mem_cap = float(_rand_normal_pos(1.0, 0.15)[0])
        machine_events_rows.append({
            "timestamp": base_time_us,
            "machine_id": int(mid),
            "event_type": 0,
            "platform_id": str(np.random.choice(platform_ids)),
            "capacity_cpu": cpu_cap,
            "capacity_memory": mem_cap,
        })
    machine_events = pd.DataFrame(machine_events_rows, columns=MACHINE_EVENT_COLS)

    vm_type_labels = []
    for _ in range(num_tasks):
        r = np.random.rand()
        if r < 0.33:
            vm_type_labels.append("cpu_intensive")
        elif r < 0.66:
            vm_type_labels.append("memory_intensive")
        else:
            vm_type_labels.append("balanced")

    task_events_rows = []
    job_events_rows = []
    task_usage_rows = []

    task_idx = 0
    for i, vm_type in enumerate(vm_type_labels):
        job_id = 1000 + (i // 10)
        task_within_job = i % 10
        arrival_offset = int(
            np.random.uniform(0, interval_us * num_intervals * 0.6)
        )
        submit_time = base_time_us + arrival_offset
        schedule_time = submit_time + int(np.random.uniform(1_000, 100_000))
        finish_time = schedule_time + window_us + int(
            np.random.uniform(interval_us, interval_us * (num_intervals - 2))
        )
        mid = int(np.random.choice(machine_ids))
        sched_class = int(np.random.choice([0, 1, 2, 3]))
        priority = int(np.random.choice(range(12)))

        if vm_type == "cpu_intensive":
            cpu_req = float(_rand_normal_pos(0.35, 0.08)[0])
            mem_req = float(_rand_normal_pos(0.12, 0.04)[0])
            cpu_usage_mean = float(_rand_normal_pos(0.6, 0.15)[0])
            mem_usage_mean = float(_rand_normal_pos(0.15, 0.05)[0])
        elif vm_type == "memory_intensive":
            cpu_req = float(_rand_normal_pos(0.12, 0.04)[0])
            mem_req = float(_rand_normal_pos(0.35, 0.08)[0])
            cpu_usage_mean = float(_rand_normal_pos(0.15, 0.05)[0])
            mem_usage_mean = float(_rand_normal_pos(0.6, 0.15)[0])
        else:
            cpu_req = float(_rand_normal_pos(0.22, 0.06)[0])
            mem_req = float(_rand_normal_pos(0.22, 0.06)[0])
            cpu_usage_mean = float(_rand_normal_pos(0.35, 0.1)[0])
            mem_usage_mean = float(_rand_normal_pos(0.35, 0.1)[0])

        disk_req = float(_rand_normal_pos(0.1, 0.04)[0])
        uid = f"user_{(job_id % 50)}"

        task_events_rows.append({
            "timestamp": submit_time,
            "missing_info": "",
            "job_id": job_id,
            "task_index": task_within_job,
            "machine_id": None,
            "event_type": 0,
            "user": uid,
            "scheduling_class": sched_class,
            "priority": priority,
            "cpu_request": cpu_req,
            "memory_request": mem_req,
            "disk_space_request": disk_req,
            "machines_restriction": False,
        })
        task_events_rows.append({
            "timestamp": schedule_time,
            "missing_info": "",
            "job_id": job_id,
            "task_index": task_within_job,
            "machine_id": mid,
            "event_type": 1,
            "user": uid,
            "scheduling_class": sched_class,
            "priority": priority,
            "cpu_request": cpu_req,
            "memory_request": mem_req,
            "disk_space_request": disk_req,
            "machines_restriction": False,
        })
        task_events_rows.append({
            "timestamp": finish_time,
            "missing_info": "",
            "job_id": job_id,
            "task_index": task_within_job,
            "machine_id": mid,
            "event_type": 4,
            "user": uid,
            "scheduling_class": sched_class,
            "priority": priority,
            "cpu_request": cpu_req,
            "memory_request": mem_req,
            "disk_space_request": disk_req,
            "machines_restriction": False,
        })

        if (i % 10) == 0:
            job_events_rows.append({
                "timestamp": submit_time,
                "missing_info": "",
                "job_id": job_id,
                "event_type": 0,
                "user": uid,
                "scheduling_class": sched_class,
                "job_name": f"jname_{job_id}",
                "logical_job_name": f"lname_{job_id // 7}",
            })

        cur_time = schedule_time
        step_idx = 0
        while cur_time + interval_us < finish_time:
            cpu_noise = np.random.normal(0, 0.08)
            mem_noise = np.random.normal(0, 0.08)
            cpu_v = float(np.clip(cpu_usage_mean + cpu_noise, 0.001, 0.999))
            mem_v = float(np.clip(mem_usage_mean + mem_noise, 0.001, 0.999))
            cpu_sample_v = float(np.clip(cpu_v + np.random.normal(0, 0.1), 0.001, 0.999))
            disk_io = float(_rand_normal_pos(0.1, 0.05)[0])
            cpi_v = float(_rand_normal_pos(1.2, 0.3)[0])
            mai_v = float(_rand_normal_pos(0.5, 0.2)[0])

            task_usage_rows.append({
                "start_time": cur_time,
                "end_time": cur_time + interval_us,
                "job_id": job_id,
                "task_index": task_within_job,
                "machine_id": mid,
                "cpu_rate": cpu_v,
                "canonical_memory_usage": mem_v,
                "assigned_memory_usage": mem_v * 1.05,
                "unmapped_page_cache": mem_v * 0.1,
                "total_page_cache": mem_v * 0.15,
                "max_memory_usage": min(mem_v * 1.2, 0.999),
                "disk_io_time": disk_io,
                "local_disk_space_used": disk_req * (0.9 + step_idx * 0.01),
                "cpu_rate_sample": cpu_sample_v,
                "cpi": cpi_v,
                "mai": mai_v,
                "sample_portality": 0.0,
                "agg_type_used_cpu": 0,
                "agg_type_used_memory": 0,
            })
            cur_time += interval_us
            step_idx += 1
        task_idx += 1

    task_events = pd.DataFrame(task_events_rows, columns=EVENT_COLS)
    job_events = pd.DataFrame(job_events_rows, columns=JOB_EVENT_COLS)
    task_usage = pd.DataFrame(task_usage_rows, columns=USAGE_COLS)

    print(f"       Generated task_events : {len(task_events):,} rows")
    print(f"       Generated job_events  : {len(job_events):,} rows")
    print(f"       Generated task_usage  : {len(task_usage):,} rows")
    print(f"       Generated machine_evts: {len(machine_events):,} rows")

    raw_dir = os.path.join(data_path)
    os.makedirs(os.path.join(raw_dir, "task_events"), exist_ok=True)
    os.makedirs(os.path.join(raw_dir, "job_events"), exist_ok=True)
    os.makedirs(os.path.join(raw_dir, "task_usage"), exist_ok=True)
    os.makedirs(os.path.join(raw_dir, "machine_events"), exist_ok=True)

    for name, df, cols in [
        ("task_events", task_events, EVENT_COLS),
        ("job_events", job_events, JOB_EVENT_COLS),
        ("task_usage", task_usage, USAGE_COLS),
        ("machine_events", machine_events, MACHINE_EVENT_COLS),
    ]:
        out_path = os.path.join(raw_dir, name, "part-00000-of-00001.csv.gz")
        with gzip.open(out_path, "wt") as f:
            df.to_csv(f, header=False, index=False)

    print(f"       Synthetic files written under {raw_dir}/")
    print("=" * 70)
    return task_usage, task_events, job_events, machine_events
