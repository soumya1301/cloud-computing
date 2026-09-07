# VM Placement Optimization — Google Cluster Workload Trace Pipeline

Implementation of the data preprocessing pipeline from the paper:

**A machine learning technique for optimizing virtual machine placement in data-centres**  
Abdullah Alelyani, Amitava Datta, Ghulam Mubashar Hassan  
*Journal of Cloud Computing*, Volume 15, Article 37, 2026  
DOI: [10.1186/s13677-026-00851-3](https://link.springer.com/article/10.1186/s13677-026-00851-3)

This repository implements:
- Loading the **official Google Cluster Workload Trace** (`clusterdata-2011-2`)
- Preprocessing exactly as described in the paper (arrival features + 5-minute workload history)
- VM type classification (CPU-intensive / memory-intensive / balanced)
- Temporal train/test splitting
- Dataset validation + helpful error messages
- Synthetic sample mode for code-pipeline testing

---

## Dataset (Official — NOT synthetic)

- **Dataset**: Google Cluster Workload Trace
- **Version**: `clusterdata-2011-2`
- **Official Source**: https://github.com/google/cluster-data
- **Release Notes**: https://github.com/google/cluster-data/blob/master/ClusterData2011_2.md
- **Schema (v2.1)**: https://drive.google.com/file/d/0B5g07T_gRDg9Z0lsSTEtTWtpOW8/view
- **Total Size (compressed)**: ~41 GB
- **License**: CC-BY 4.0

### Exact file placement in this project

Download the trace into `data/google_cluster/raw/` so the final layout matches:

```
cloud/
├── main.py
├── requirements.txt
├── config/
│   └── config.yaml
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── dataset_validator.py
│   ├── data_loader.py
│   ├── preprocessing.py
│   └── sample_mode.py
└── data/
    └── google_cluster/
        ├── README.md              ← detailed dataset & schema docs
        └── raw/                   ← ↓ ↓ place downloaded files here ↓ ↓
            ├── machine_events/
            │   └── part-?????-of-00001.csv.gz
            ├── machine_attributes/
            │   └── part-?????-of-00001.csv.gz
            ├── job_events/
            │   └── part-?????-of-00500.csv.gz
            ├── task_events/
            │   └── part-?????-of-00500.csv.gz
            └── task_usage/
                └── part-?????-of-00500.csv.gz
```

### Quick download (once authenticated with gcloud)

```bash
# 1. Join the mailing list (required — see data/google_cluster/README.md)
# 2. Install gcloud SDK & authenticate
gcloud auth login

# 3. Download the FULL trace (≈ 41 GB compressed)
gcloud storage cp -r gs://clusterdata-2011-2/* ./data/google_cluster/raw/
```

For more detail (schema, columns, partial-download commands, trace anomalies),
see [data/google_cluster/README.md](data/google_cluster/README.md).

---

## Installation

```bash
cd /path/to/cloud
python3 -m venv .venv && source .venv/bin/activate     # optional, recommended
pip install -r requirements.txt
```

---

## Usage

All commands are run from the project root.

### 1. Validate that the dataset is in place

```bash
python main.py --validate
```

If the dataset is missing, the program prints a **clear, actionable error**
that explains exactly which directory and which files are required, how to
download them, and where to place them.

### 2. Run the full pipeline (real Google dataset)

```bash
python main.py --data_path ./data/google_cluster/raw/
```

`--data_path` is configurable. Defaults to `./data/google_cluster/raw/`.

Optional flags:
- `--max_parts N` — load only the first `N` part files per table (for quick
  smoke tests on the real data without the full 41 GB).

### 3. TEST MODE — synthetic sample (NOT for paper results)

```bash
python main.py --sample_mode
```

Generates a small synthetic dataset with the *same schema* as the Google trace
and runs the full pipeline on it. **This is only for testing code flow; its
output must never be reported as the paper's experimental results.**

Sample mode is clearly labelled in every output, and the final summary reminds
the user that the results are synthetic.

### 4. Using a custom config

```bash
python main.py --config_path ./config/config.yaml
```

All thresholds, columns, train/test ratios, scaling, and sample-mode knobs
live in [`config/config.yaml`](config/config.yaml).

---

## Preprocessing steps (per the paper)

The preprocessing is implemented in [`src/preprocessing.py`](src/preprocessing.py).
Each step is documented in detail in the dataset README and in code docstrings.

| Step | What we do |
|------|------------|
| 1. Missing values | Drop rows missing required `cpu_rate` or `canonical_memory_usage`; warn on high-missing columns |
| 2. Task lifecycle | Join task_events SUBMIT / SCHEDULE / FINISH to get t=0 per task |
| 3. Observation window | Select only the **first 5 minutes of task_usage** after each task's `schedule_time` (per paper: observing resource usage "for a short period after their arrival") |
| 4. Per-task feature vector | Aggregate CPU/memory/sample/disk stats: mean, std, min, max, count + arrival features (`cpu_request`, `memory_request`, `scheduling_class`, `priority`) + CPU-to-memory ratio |
| 5. VM-type label | Threshold the CPU/memory ratio into `cpu_intensive` / `memory_intensive` / `balanced` |
| 6. History sequences | Fixed-length 6-step × 4-channel sequences of `[cpu_rate, mem, cpu_sample, disk]` over the 5-min window |
| 7. Scaling | Min-max re-scale (schema fields are already [0,1] normalised to avg-machine capacity) |
| 8. Split | **Temporal** 80/10/10 train/val/test by arrival order — never random — so we respect causality |

Columns actually used from each trace table are listed in
[`data/google_cluster/README.md`](data/google_cluster/README.md) under
*"Files / Columns Actually Used By This Implementation"*.

---

## Reproducibility

When reporting results:

> **Dataset**: Google Cluster Workload Trace  
> **Version**: clusterdata-2011-2  
> **Official Source**: https://github.com/google/cluster-data  
>
> Downloaded files were placed in `<project>/data/google_cluster/raw/` as
> described in the dataset README (see `data/google_cluster/README.md`).
> Train/test were split temporally 80/20 by task arrival time using the
> default `--data_path ./data/google_cluster/raw/` and `config/config.yaml`.

---

## Project layout

```
cloud/
├── main.py                    ← CLI entry point
├── requirements.txt
├── README.md                  ← this file
├── config/
│   └── config.yaml            ← all tunable parameters
├── src/
│   ├── __init__.py
│   ├── config.py              ← YAML config loader
│   ├── dataset_validator.py   ← dataset existence checks + clear errors
│   ├── data_loader.py         ← loads gzipped CSV parts into DataFrames
│   ├── preprocessing.py       ← paper's 6-step preprocessing pipeline
│   └── sample_mode.py         ← synthetic TEST-MODE generator
└── data/
    └── google_cluster/
        ├── README.md          ← full dataset documentation (schema, download, setup)
        └── raw/               ← user places Google trace here (not committed)
```
