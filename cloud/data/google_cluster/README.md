# Google Cluster Workload Trace Dataset Setup

## Official Dataset Information

- **Dataset**: Google Cluster Workload Trace
- **Version**: clusterdata-2011-2 (v2.1)
- **Official Source**: https://github.com/google/cluster-data
- **Documentation**: https://github.com/google/cluster-data/blob/master/ClusterData2011_2.md
- **Schema Document (v2.1)**: https://drive.google.com/file/d/0B5g07T_gRDg9Z0lsSTEtTWtpOW8/view
- **Total Compressed Size**: Approximately 41 GB
- **License**: CC-BY (Creative Commons Attribution 4.0 International)

## Dataset Description

The `clusterdata-2011-2` trace represents 29 days of Borg cell information from May 2011, on a cluster of about 12,500 machines. The trace starts at 19:00 EDT on Sunday May 1, 2011 (trace timestamp 600s). The datacenter is in the US Eastern timezone.

Version 2.1 adds a single new column to the `task_usage` tables: a randomly-picked 1-second sample of CPU usage from within the associated 5-minute usage-reporting period.

## Download Instructions

### Prerequisites

1. Join the Google Cluster Data mailing list (required):
   - URL: https://groups.google.com/forum/#!forum/googleclusterdata-discuss
   - **Important**: Fill out the "reason" field, or your application will be rejected.

2. Install the Google Cloud SDK (`gcloud`):
   - URL: https://docs.cloud.google.com/sdk/docs/install-sdk

### Download Using gcloud Storage CLI

The trace is stored in the Google Storage bucket `clusterdata-2011-2`.

```bash
# Authenticate with Google Cloud
gcloud auth login

# List all available files in the bucket
gcloud storage ls gs://clusterdata-2011-2/

# Download all files (WARNING: ~41 GB compressed)
gcloud storage cp -r gs://clusterdata-2011-2/* ./data/google_cluster/raw/
```

### Partial Download (Recommended for Initial Testing)

For initial testing, you can download only the required tables from just 1-2 parts:

```bash
# Download just one part of each required table
gcloud storage cp gs://clusterdata-2011-2/task_events/part-00000-of-00500.csv.gz ./data/google_cluster/raw/task_events/
gcloud storage cp gs://clusterdata-2011-2/task_usage/part-00000-of-00500.csv.gz ./data/google_cluster/raw/task_usage/
gcloud storage cp gs://clusterdata-2011-2/job_events/part-00000-of-00500.csv.gz ./data/google_cluster/raw/job_events/
gcloud storage cp gs://clusterdata-2011-2/machine_events/part-00000-of-00001.csv.gz ./data/google_cluster/raw/machine_events/
gcloud storage cp gs://clusterdata-2011-2/machine_attributes/part-00000-of-00001.csv.gz ./data/google_cluster/raw/machine_attributes/
```

## Required Directory Structure

After downloading, the directory `./data/google_cluster/raw/` must contain the following subdirectories with CSV.gz files:

```
data/google_cluster/raw/
├── machine_events/
│   └── part-?????-of-00001.csv.gz
├── machine_attributes/
│   └── part-?????-of-00001.csv.gz
├── job_events/
│   └── part-?????-of-00500.csv.gz
├── task_events/
│   └── part-?????-of-00500.csv.gz
├── task_usage/
│   └── part-?????-of-00500.csv.gz
└── constraints/
    └── part-?????-of-00500.csv.gz  (optional)
```

Each table directory contains 1 to 500 gzipped CSV part files.

## Data Format / Schema

All files are **gzip-compressed CSV** files with **no header row**. Columns are comma-separated.

### 1. Task Usage Table (task_usage/) — PRIMARY TABLE USED

This is the most important table. It contains resource usage measurements at 5-minute intervals for each task.

**Columns (indexes 0-based):**

| Index | Column Name | Description | Unit / Notes |
|-------|-------------|-------------|--------------|
| 0 | start_time | Start of measurement interval | Microseconds since trace start |
| 1 | end_time | End of measurement interval | Microseconds since trace start |
| 2 | job_id | Job identifier | Unique per job |
| 3 | task_index | Task index within job | 0-based |
| 4 | machine_id | Machine the task ran on | Unique per machine |
| 5 | cpu_rate | Mean CPU usage rate | Normalized [0,1] per average machine CPU capacity |
| 6 | canonical_memory_usage | Memory usage (canonical) | Normalized [0,1] per average machine memory capacity |
| 7 | assigned_memory_usage | Memory usage (assigned) | Normalized per machine memory ratio |
| 8 | unmapped_page_cache | Unmapped page cache memory | Normalized |
| 9 | total_page_cache | Total page cache memory | Normalized |
| 10 | max_memory_usage | Maximum memory usage observed | Normalized |
| 11 | disk_io_time | Fraction of time disk I/O was active | [0,1] |
| 12 | local_disk_space_used | Local disk space used | Normalized |
| 13 | **cpu_rate_sample** | 1-second CPU usage sample (v2.1) | Normalized [0,1]. Random 1s within 5min window. |
| 14 | cycles_per_instruction (CPI) | Cycles per instruction | Ratio |
| 15 | memory_accesses_per_instruction (MAI) | Memory accesses per instruction | Ratio |
| 16 | sample_portality | (deprecated) | — |
| 17 | agg_type_used_cpu | Aggregated sample type for CPU | Classification of sample |
| 18 | agg_type_used_memory | Aggregated sample type for memory | Classification of sample |

### 2. Task Events Table (task_events/) — USED

Records scheduling events for each task (submit, schedule, evict, finish, etc.).

**Columns:**

| Index | Column Name | Description |
|-------|-------------|-------------|
| 0 | timestamp | Event timestamp | Microseconds |
| 1 | missing_info | Non-empty if any fields were missing | Set of field numbers, comma separated |
| 2 | job_id | Job ID |
| 3 | task_index | Task index within job |
| 4 | machine_id | Machine ID (may be empty) |
| 5 | event_type | Event type code: 0=SUBMIT, 1=SCHEDULE, 2=EVICT, 3=FAIL, 4=FINISH, 5=KILL, 6=LOST, 7=UPDATE_PENDING, 8=UPDATE_RUNNING |
| 6 | user | Username (hash) |
| 7 | scheduling_class | Scheduling class / priority | 0-3 |
| 8 | priority | Task priority | 0-11 (0,1=free; 9,10,11=production; 12=monitoring) |
| 9 | cpu_request | Requested CPU capacity | Normalized [0,1] |
| 10 | memory_request | Requested memory capacity | Normalized [0,1] |
| 11 | disk_space_request | Requested disk space | Normalized [0,1] |
| 12 | machines_restriction | Different machines restriction flag | Boolean |

### 3. Job Events Table (job_events/) — USED

Records scheduling events for each job.

**Columns:**

| Index | Column Name | Description |
|-------|-------------|-------------|
| 0 | timestamp | Event timestamp | Microseconds |
| 1 | missing_info | Non-empty if any fields were missing |
| 2 | job_id | Job ID |
| 3 | event_type | Event type code | Same as task events |
| 4 | user | Username (hash) |
| 5 | scheduling_class | Scheduling class | 0-3 |
| 6 | job_name | Job name (hash) |
| 7 | logical_job_name | Logical job name (hash) |

### 4. Machine Events Table (machine_events/) — USED

Records add/remove/update events for each machine.

**Columns:**

| Index | Column Name | Description |
|-------|-------------|-------------|
| 0 | timestamp | Event timestamp | Microseconds |
| 1 | machine_id | Machine ID |
| 2 | event_type | Event type: 0=ADD, 1=REMOVE, 2=UPDATE |
| 3 | platform_id | Platform/CPU microarchitecture | Hash |
| 4 | capacity_cpu | Machine CPU capacity | Normalized, mean=~1.0 |
| 5 | capacity_memory | Machine memory capacity | Normalized, mean=~1.0 |

### 5. Machine Attributes Table (machine_attributes/) — OPTIONAL

Records per-machine attributes.

**Columns:**

| Index | Column Name | Description |
|-------|-------------|-------------|
| 0 | timestamp | Event timestamp | Microseconds |
| 1 | machine_id | Machine ID |
| 2 | attribute_name | Attribute name (hash) |
| 3 | attribute_value | Attribute value (hash) |
| 4 | attribute_deleted | Whether attribute was deleted | Boolean |

## Files / Columns Actually Used By This Implementation

Based on the paper "A machine learning technique for optimizing virtual machine placement in data-centres" (Alelyani et al., 2026):

### Required Tables:
1. **task_usage/** — Primary data source for workload history
2. **task_events/** — Task lifecycle events (submit/schedule/finish times)
3. **job_events/** — Job metadata and scheduling class
4. **machine_events/** — Machine capacity information

### Required Columns:

**From task_usage:**
- Index 2 (`job_id`) — Join key with task_events
- Index 3 (`task_index`) — Identifies individual task within job
- Index 4 (`machine_id`) — Machine assignment
- Index 5 (`cpu_rate`) — Mean CPU utilization over 5-min window (core metric)
- Index 6 (`canonical_memory_usage`) — Memory utilization (core metric)
- Index 13 (`cpu_rate_sample`) — 1-second CPU sample for variance
- Index 0 (`start_time`) — For time-window construction

**From task_events:**
- Index 2 (`job_id`) / Index 3 (`task_index`) — Join keys
- Index 0 (`timestamp`) — Submit/schedule/finish timestamps
- Index 5 (`event_type`) — Determine task lifecycle state
- Index 9 (`cpu_request`) — Requested CPU at submission
- Index 10 (`memory_request`) — Requested memory at submission
- Index 7 (`scheduling_class`) — Priority class feature
- Index 8 (`priority`) — Exact priority value

**From job_events:**
- Index 2 (`job_id`) — Join key
- Index 5 (`scheduling_class`) — Job-level scheduling class
- Index 0 (`timestamp`) / Index 3 (`event_type`) — Job submit time

**From machine_events:**
- Index 1 (`machine_id`) — Join key
- Index 4 (`capacity_cpu`) — Machine CPU capacity (for utilization scaling)
- Index 5 (`capacity_memory`) — Machine memory capacity (for utilization scaling)
- Index 3 (`platform_id`) — CPU platform classification

## Time Intervals

- **Workload sampling interval**: 5 minutes (300 seconds = 300,000,000 microseconds)
- **Workload history window**: First 5 minutes after task arrival (per paper: "observing their resource usage for a short period after their arrival")
- **Trace total duration**: 29 days
- **Trace start timestamp**: 600 seconds (corresponds to 19:00 EDT May 1, 2011)

## CPU and Memory Utilization Calculation

Per the Google cluster data schema:
- `cpu_rate` is the mean CPU usage rate, **normalized to the average machine's total CPU capacity**.
- `canonical_memory_usage` is memory usage **normalized to the average machine's total memory capacity**.

For this implementation, utilization metrics are computed as:
1. **Per-task CPU utilization (%)** = `cpu_rate` * 100 (already normalized to average machine CPU)
2. **Per-task memory utilization (%)** = `canonical_memory_usage` * 100 (already normalized to average machine memory)
3. If per-machine scaling is needed: `utilization_on_machine = usage_value / machine_capacity_*`

## VM / Task Record Construction

Each unique task is identified by the composite key `(job_id, task_index)`. For each task, we construct:

1. **Arrival features** (from task_events SUBMIT event):
   - Requested CPU (`cpu_request`)
   - Requested memory (`memory_request`)
   - Scheduling class
   - Priority level
   - Arrival timestamp

2. **5-minute workload history features** (from task_usage, first 5min after schedule):
   - CPU rate at each 5-min interval (1 interval for immediate observation)
   - Canonical memory usage at each 5-min interval
   - CPU rate sample (1s) value
   - Mean, min, max, std of CPU over the observation window
   - Mean, min, max, std of memory over the observation window
   - CPU-to-memory ratio

3. **Derived label** (VM type classification):
   - CPU-intensive: CPU utilization >> memory utilization (ratio > threshold)
   - Memory-intensive: Memory utilization >> CPU utilization (ratio < 1/threshold)
   - Communication-intensive / Balanced: Otherwise

## Missing Value Handling

Per the trace documentation:
- ~0.013% of task events and ~0.0008% of job events have non-empty `missing_info` fields.
- < 0.05% of scheduling event records are estimated missing.
- < 1% of resource usage measurements are estimated missing.
- Some CPI/MAI values are clearly inaccurate (out of plausible range).

This implementation handles missing values as follows:
1. Rows with missing `cpu_rate` or `canonical_memory_usage` are dropped (imputation not recommended for time-series utilization).
2. For rows with missing optional columns (CPI, MAI, disk), the column is excluded from features for that record.
3. Tasks that have a SUBMIT event but no task_usage records within the first 15 minutes are flagged and excluded from training.
4. Outlier/invalid CPI/MAI values are filtered out if those features are used.

## Normalization / Scaling

Per the schema, core utilization fields (`cpu_rate`, `canonical_memory_usage`, `cpu_request`, `memory_request`, etc.) are already **pre-normalized** to [0, 1] relative to the average machine's capacity.

Additional scaling applied in this implementation:
1. **Feature-wise min-max scaling** to [0, 1] is re-applied after feature engineering (e.g., for min/max/std aggregations, ratios, and history sequences).
2. Arrival timestamps are normalized relative to trace start (t0 = 600s) and then divided by trace total duration.
3. 5-minute history sequences are kept as normalized vectors (already in [0,1] from schema, then optionally standardized per task).

## 5-Minute Workload History Construction

For each task (job_id, task_index):
1. Find the SCHEDULE event timestamp from task_events (event_type = 1).
2. Query task_usage records where:
   - `task_usage.job_id == job_id`
   - `task_usage.task_index == task_index`
   - `task_usage.start_time >= schedule_timestamp`
   - `task_usage.start_time < schedule_timestamp + 5 minutes (300s = 300_000_000 us)`
3. Aggregate these records into a fixed-length sequence:
   - If only 1 record: repeat/single-element sequence
   - If multiple sub-intervals: concatenate in chronological order
   - Each time step contains: `[cpu_rate, canonical_memory_usage, cpu_rate_sample, disk_io_time]`
4. Compute summary statistics (mean, std, min, max) over the window for CPU and memory separately.
5. CPU-to-memory ratio = mean(CPU rate) / max(mean(memory), epsilon).

## Training / Testing Data Split

This implementation uses:
- **Training set**: First 80% of tasks by arrival time (approximately the first 23 days of the 29-day trace).
- **Test set**: Last 20% of tasks by arrival time (last ~6 days).
- **Validation split**: 10% of the training set held out for hyperparameter tuning.
- **No random splitting**: Tasks are split strictly by arrival order to respect temporal causality (you cannot train on a task that arrives after a test task).

This aligns with typical time-series workload evaluation setups.

## Known Trace Anomalies To Handle

1. **Disk-time-fraction data**: Only present in the first ~14 days; use disk features cautiously or impute/drop for later periods.
2. **Job 6253771429**: Retains its job ID after being stopped/reconfigured/restarted; handled by dedup on latest events per job_id.
3. **~70 jobs** (e.g., job 6377830001): Have job events but no task events because tasks were disabled their entire duration. These are skipped.
4. **CPI/MAI inaccuracy**: Filter values that are clearly outside the plausible range for the underlying micro-architectures, or drop these features.

## Verifying Dataset Setup

Run the main script with validation:

```bash
python main.py --data_path ./data/google_cluster/raw/ --validate
```

If the dataset is missing, the program will print a clear message explaining exactly where files must be placed.

## Test / Sample Mode

For testing the code pipeline without the full 41 GB dataset, use:

```bash
python main.py --sample_mode
```

This generates a small synthetic sample of records matching the Google trace schema, purely for testing code flow and ML pipeline correctness. **Results from sample mode must NOT be used as experimental results for the paper.**
