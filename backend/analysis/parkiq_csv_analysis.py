"""
ParkIQ historical analytics over the real Jan-May Bengaluru violation
dataset (298,450 rows, Nov 2023-Apr 2024 by actual timestamp -- the
filename says "jan to may" but the real data spans those calendar months
instead; flag that discrepancy if quoting "January-May data" anywhere).

This is a one-time batch job, not a live service: violations history
doesn't change minute to minute, so the output JSON files are meant to be
served as static reads from the BTP-Niyantran /api/parkiq/* endpoints
rather than recomputed per request. Re-run this script if a fresher CSV
export becomes available.

Outputs four JSON files matching the endpoints already defined in the
Bengluru-smart-traffic README:
  clusters.json            -> GET /api/parkiq/clusters
  congestion_scores.json   -> GET /api/parkiq/congestion-scores
  deterrence_decay.json    -> GET /api/parkiq/deterrence-decay
  heatmap.json             -> GET /api/parkiq/heatmap

Honesty note on congestion scoring: real road-capacity data (OSM) isn't
reachable from this environment, so "congestion score" here is a relative
0-10 index built from violation density and a vehicle-type severity weight
(a bus or LGV blocks far more carriageway than a scooter), not an
absolute BPR delay-in-minutes figure. Swap in real per-road capacity if
that becomes available -- the formula is isolated in `congestion_score()`
below for exactly that reason.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

CSV_PATH = "/mnt/user-data/uploads/1781721560635_jan_to_may_police_violation_anonymized791b166.csv"
OUT_DIR = Path(__file__).parent / "output"
OUT_DIR.mkdir(exist_ok=True)

# Wider vehicles consume more carriageway width per illegal-parking minute.
# Hackathon-grade relative weights, not a measured standard.
VEHICLE_SEVERITY_WEIGHT = {
    "PRIVATE BUS": 3.0, "MAXI-CAB": 2.2, "VAN": 1.8, "LGV": 1.8,
    "GOODS AUTO": 1.4, "CAR": 1.3, "PASSENGER AUTO": 1.2,
    "MOTOR CYCLE": 0.6, "SCOOTER": 0.6, "MOPED": 0.5,
}


def load() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df["created_dt"] = pd.to_datetime(df["created_datetime"], errors="coerce", utc=True)
    df["primary_violation"] = (
        df["violation_type"].str.strip("[]").str.replace('"', "", regex=False).str.split(",").str[0]
    )
    df["severity_weight"] = df["vehicle_type"].map(VEHICLE_SEVERITY_WEIGHT).fillna(1.0)
    return df


def repeat_offender_stats(df: pd.DataFrame) -> dict:
    counts = df["vehicle_number"].value_counts()
    repeat_vehicles = counts[counts > 1]
    total_vehicles = len(counts)
    total_rows = len(df)

    sorted_counts = counts.sort_values(ascending=False)
    cum_violations = sorted_counts.cumsum()
    top10_pct_vehicle_n = max(1, int(total_vehicles * 0.10))
    violations_from_top10pct = int(cum_violations.iloc[top10_pct_vehicle_n - 1])

    return {
        "total_unique_vehicles": int(total_vehicles),
        "vehicles_with_repeat_violations": int(len(repeat_vehicles)),
        "repeat_vehicle_share_pct": round(len(repeat_vehicles) / total_vehicles * 100, 1),
        "violations_from_repeat_vehicles": int(repeat_vehicles.sum()),
        "violations_from_repeat_vehicles_share_pct": round(repeat_vehicles.sum() / total_rows * 100, 1),
        "top10pct_vehicles_violation_share_pct": round(violations_from_top10pct / total_rows * 100, 1),
        "most_frequent_vehicle_violation_count": int(sorted_counts.iloc[0]),
        "note": "vehicle_number is anonymized but appears consistently mapped per real vehicle, not re-randomized per row -- repeat-offender tracking is genuinely supported by this dataset.",
    }


def named_junction_ranking(df: pd.DataFrame, top_n: int = 12) -> list:
    named = df[df["junction_name"] != "No Junction"].copy()
    grouped = named.groupby("junction_name").agg(
        violation_count=("id", "count"),
        avg_severity=("severity_weight", "mean"),
        lat=("latitude", "mean"),
        lng=("longitude", "mean"),
    )
    max_count = grouped["violation_count"].max()
    grouped["congestion_score"] = (
        (grouped["violation_count"] / max_count) * 7 + (grouped["avg_severity"] / grouped["avg_severity"].max()) * 3
    ).round(2)
    grouped = grouped.sort_values("violation_count", ascending=False).head(top_n)
    return [
        {
            "junction": idx,
            "violation_count": int(row.violation_count),
            "congestion_score": float(row.congestion_score),
            "lat": round(float(row.lat), 5),
            "lng": round(float(row.lng), 5),
        }
        for idx, row in grouped.iterrows()
    ]


def run_hdbscan(df: pd.DataFrame, sample_n: int = 60000) -> list:
    import hdbscan

    pts = df[["latitude", "longitude"]].dropna()
    if len(pts) > sample_n:
        pts = pts.sample(sample_n, random_state=42)

    clusterer = hdbscan.HDBSCAN(min_cluster_size=80, min_samples=15, core_dist_n_jobs=-1)
    labels = clusterer.fit_predict(pts.values)
    pts = pts.assign(cluster=labels)
    real_clusters = pts[pts["cluster"] >= 0]

    summary = (
        real_clusters.groupby("cluster")
        .agg(lat=("latitude", "mean"), lng=("longitude", "mean"), point_count=("latitude", "size"))
        .sort_values("point_count", ascending=False)
    )
    scale_factor = len(pts) / sample_n if sample_n < len(df) else 1.0
    return [
        {
            "cluster_id": int(idx),
            "lat": round(float(row.lat), 5),
            "lng": round(float(row.lng), 5),
            "sampled_point_count": int(row.point_count),
            "estimated_full_dataset_count": int(round(row.point_count / (sample_n / len(df)))),
        }
        for idx, row in summary.head(20).iterrows()
    ]


def deterrence_decay(df: pd.DataFrame, junction: str) -> dict:
    sub = df[df["junction_name"] == junction].copy()
    daily = sub.set_index("created_dt").resample("1D").size()
    daily = daily[daily.index.notna()]

    baseline = daily.rolling(14, min_periods=7).median()
    drop_ratio = daily / baseline
    drop_days = drop_ratio[(drop_ratio < 0.5) & (baseline > 3)].index

    if len(drop_days) == 0:
        return {"junction": junction, "found_drop_event": False, "series": _series(daily)}

    drop_day = drop_days[0]
    pre_level = baseline.loc[drop_day]
    after = daily.loc[drop_day:]
    recovered = after[after >= pre_level * 0.8]
    days_to_recover = (
        int((recovered.index[1] - drop_day).days) if len(recovered) > 1 else None
    )

    window = daily.loc[drop_day - pd.Timedelta(days=5): drop_day + pd.Timedelta(days=21)]
    return {
        "junction": junction,
        "found_drop_event": True,
        "drop_date": str(drop_day.date()),
        "pre_drop_baseline_per_day": round(float(pre_level), 1),
        "days_to_80pct_recovery": days_to_recover,
        "series": _series(window),
    }


def _series(s: pd.Series) -> list:
    return [{"date": str(idx.date()), "violations": int(v)} for idx, v in s.items()]


def heatmap_hour_by_dow(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["created_dt"]).copy()
    d["hour"] = d["created_dt"].dt.hour
    d["dow"] = d["created_dt"].dt.day_name()
    pivot = d.pivot_table(index="dow", columns="hour", values="id", aggfunc="count", fill_value=0)
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pivot = pivot.reindex(dow_order)
    return {"days": dow_order, "hours": list(range(24)), "matrix": pivot.values.tolist()}


def main() -> None:
    df = load()
    print(f"Loaded {len(df)} rows, {df['created_dt'].notna().sum()} with valid timestamps")

    repeat_stats = repeat_offender_stats(df)
    print("Repeat offender stats:", json.dumps(repeat_stats, indent=2))

    junctions = named_junction_ranking(df)
    print(f"\nTop junction: {junctions[0]['junction']} ({junctions[0]['violation_count']} violations)")

    clusters = run_hdbscan(df)
    print(f"\nHDBSCAN found {len(clusters)} real spatial clusters (top by estimated full-dataset count):")
    for c in clusters[:5]:
        print(f"  {c}")

    top_junction_name = junctions[0]["junction"]
    decay = deterrence_decay(df, top_junction_name)
    print(f"\nDeterrence decay for {top_junction_name}:", json.dumps({k: v for k, v in decay.items() if k != "series"}, indent=2))

    heatmap = heatmap_hour_by_dow(df)

    (OUT_DIR / "clusters.json").write_text(json.dumps({"clusters": clusters}, indent=2))
    (OUT_DIR / "congestion_scores.json").write_text(json.dumps({"junctions": junctions}, indent=2))
    (OUT_DIR / "deterrence_decay.json").write_text(json.dumps(decay, indent=2))
    (OUT_DIR / "heatmap.json").write_text(json.dumps(heatmap, indent=2))
    (OUT_DIR / "repeat_offender_stats.json").write_text(json.dumps(repeat_stats, indent=2))
    print(f"\nWrote 5 JSON files to {OUT_DIR}")


if __name__ == "__main__":
    main()
