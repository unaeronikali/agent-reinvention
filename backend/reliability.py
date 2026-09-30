from datetime import datetime, timedelta, timezone


SLO_TARGET = 99.9
WINDOW_MINUTES = 30 * 24 * 60
MONTHLY_BUDGET_MINUTES = WINDOW_MINUTES * (1 - SLO_TARGET / 100)
ERROR_BUDGET_RATIO = 1 - SLO_TARGET / 100


def build_reliability_snapshot(metrics, sample_interval_seconds=2):
  error_points = sorted(
    (point for point in metrics if point["metric_name"] == "error_rate_pct"),
    key=lambda point: point["recorded_at"],
  )
  latest = error_points[-1] if error_points else None
  error_rate = max(0.0, min(100.0, float(latest["value"]))) if latest else 0.0
  availability = 100.0 - error_rate
  cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)
  consumed_minutes = 0.0
  for point in error_points:
    recorded_at = datetime.fromisoformat(point["recorded_at"].replace("Z", "+00:00"))
    if recorded_at >= cutoff:
      consumed_minutes += (max(0.0, min(100.0, float(point["value"]))) / 100) * sample_interval_seconds / 60

  remaining_minutes = max(0.0, MONTHLY_BUDGET_MINUTES - consumed_minutes)
  burn_rate = error_rate / 100 / ERROR_BUDGET_RATIO
  projected_minutes = remaining_minutes / (error_rate / 100) if error_rate > 0 else None
  latest_metrics = {}
  for point in metrics:
    if point["metric_name"] not in latest_metrics or point["recorded_at"] > latest_metrics[point["metric_name"]]["recorded_at"]:
      latest_metrics[point["metric_name"]] = point

  risk_score = 0
  reasons = []
  if burn_rate >= 14.4:
    risk_score = 2
    reasons.append(f"Error budget is burning at {burn_rate:.1f}x the allowed rate.")
  elif burn_rate >= 6:
    risk_score = 1
    reasons.append(f"Error budget is burning at {burn_rate:.1f}x the allowed rate.")
  if remaining_minutes <= MONTHLY_BUDGET_MINUTES * 0.2:
    risk_score = max(risk_score, 2)
    reasons.append("Less than 20% of the monthly error budget remains.")
  for metric_name, warning, critical, label in (
    ("response_time_ms", 1000, 3000, "Latency"),
    ("cpu_pct", 70, 90, "CPU"),
    ("memory_pct", 75, 90, "Memory"),
  ):
    point = latest_metrics.get(metric_name)
    if point and point["value"] >= critical:
      risk_score = max(risk_score, 2)
      reasons.append(f"{label} is critical at {point['value']:g}{'ms' if metric_name == 'response_time_ms' else '%'}.")
    elif point and point["value"] >= warning:
      risk_score = max(risk_score, 1)
      reasons.append(f"{label} is elevated at {point['value']:g}{'ms' if metric_name == 'response_time_ms' else '%'}.")
  risk = ("LOW", "MEDIUM", "HIGH")[risk_score]

  recommendations = []
  if error_rate >= 1:
    recommendations.append("Inspect the latest application and database errors.")
  latency = latest_metrics.get("response_time_ms")
  if latency and latency["value"] >= 1000:
    recommendations.append("Review slow requests and database connection-pool saturation.")
  cpu = latest_metrics.get("cpu_pct")
  if cpu and cpu["value"] >= 80:
    recommendations.append("Scale application capacity and check CPU-heavy workloads.")
  if not recommendations:
    recommendations.append("No immediate action. Continue watching the service-level indicators.")

  return {
    "slo_target": SLO_TARGET,
    "window_minutes": WINDOW_MINUTES,
    "availability": round(availability, 3),
    "error_rate_pct": round(error_rate, 3),
    "budget_total_minutes": round(MONTHLY_BUDGET_MINUTES, 1),
    "budget_consumed_minutes": round(consumed_minutes, 2),
    "budget_remaining_minutes": round(remaining_minutes, 2),
    "budget_remaining_pct": round(remaining_minutes / MONTHLY_BUDGET_MINUTES * 100, 1),
    "burn_rate": round(burn_rate, 1),
    "risk": risk,
    "reasons": reasons or ["Service metrics are within the selected reliability policy."],
    "minutes_to_exhaustion": round(projected_minutes, 1) if projected_minutes is not None else None,
    "recommendations": recommendations,
    "observed_at": datetime.now(timezone.utc).isoformat(),
  }