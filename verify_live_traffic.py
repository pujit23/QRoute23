"""
verify_live_traffic.py
Standalone traffic verification script.

Run directly:
    python verify_live_traffic.py

Purpose:
- Fetches real-time TomTom traffic flow across multiple realistic test coordinates (highways and dense city centers).
- Accurately tracks traffic sources (live API, in-memory cache, or offline fallback).
- Prints structured audit diagnostics and a definitive PASS/WARNING/FAIL verdict.
- Exports a timestamped JSON audit log ('traffic_audit_log.json') as immutable proof.
"""
import sys
import io

# Force UTF-8 output on Windows terminals if supported
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from traffic_provider import (
    get_traffic_flow,
    get_audit_log,
    get_audit_summary,
    export_audit_log,
    clear_audit_log
)

TEST_POINTS = [
    {"name": "Jaipur Bypass / NH48 Corridor", "lat": 26.9124, "lon": 75.7873},
    {"name": "MI Road (Jaipur City Center)", "lat": 26.9196, "lon": 75.7878},
    {"name": "Hawa Mahal (Old Walled City)", "lat": 26.9239, "lon": 75.8267},
    {"name": "Amer Fort Road Corridor", "lat": 26.9855, "lon": 75.8513},
    {"name": "Mansarovar Commercial Hub", "lat": 26.8530, "lon": 75.7663},
]


def run_verification() -> int:
    print("=" * 80)
    print("QUANTUM ROUTE - LIVE TOMTOM TRAFFIC VERIFICATION & AUDIT RUN")
    print("=" * 80)

    clear_audit_log()
    results = []

    print(f"\n1. Querying {len(TEST_POINTS)} distinct test coordinates...\n")
    print(f"{'#':<3} {'Location Name':<32} {'Lat/Lon':<20} {'Source':<10} {'Curr Spd':<10} {'Free Spd':<10} {'Ratio':<8} {'Conf':<6}")
    print("-" * 105)

    for idx, pt in enumerate(TEST_POINTS, 1):
        lat, lon = pt["lat"], pt["lon"]
        flow = get_traffic_flow(lat, lon)
        audit_entries = get_audit_log()
        source = audit_entries[-1]["source"] if audit_entries else "unknown"

        curr_spd = f"{flow['current_speed_kmh']:.1f} km/h" if flow['current_speed_kmh'] is not None else "N/A"
        free_spd = f"{flow['free_flow_speed_kmh']:.1f} km/h" if flow['free_flow_speed_kmh'] is not None else "N/A"
        ratio_str = f"{flow['ratio']:.3f}"
        conf_str = f"{flow['confidence']:.2f}"
        coords_str = f"{lat:.4f}, {lon:.4f}"

        print(f"{idx:<3} {pt['name']:<32} {coords_str:<20} {source:<10} {curr_spd:<10} {free_spd:<10} {ratio_str:<8} {conf_str:<6}")
        results.append(flow)

    summary = get_audit_summary()

    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)
    print(f"  * Total Calls:        {summary['total_calls']}")
    print(f"  * Live API Calls:     {summary['live_api_calls']}")
    print(f"  * Cache Hits:         {summary['cache_hits']}")
    print(f"  * Fallback Calls:     {summary['fallback_calls']}")
    print(f"  * Live Data Rate:     {summary['live_data_pct']:.1f}%")
    print(f"  * First Call Time:    {summary['first_call'] or 'N/A'}")
    print(f"  * Last Call Time:     {summary['last_call'] or 'N/A'}")

    ratios = [r['ratio'] for r in results]
    live_pct = summary['live_data_pct']
    total_calls = summary['total_calls']

    print("\n" + "=" * 80)
    print("VERDICT")
    print("=" * 80)

    exit_code = 0
    if live_pct == 0 and total_calls > 0:
        print("FAIL: All calls fell back. Check TOMTOM_API_KEY in .env and re-run the raw browser URL test from earlier.")
        exit_code = 1
    elif live_pct > 0 and all(r == 1.0 for r in ratios):
        print("WARNING: Calls reached the live API but every ratio is exactly 1.0 - this can be genuine (all sampled points have free-flow traffic right now) or a silent parsing bug. Cross-check by picking one of these points and testing the raw browser URL directly to compare currentSpeed vs freeFlowSpeed by hand.")
    elif live_pct > 0 and any(r != 1.0 for r in ratios):
        print(f"PASS: Live traffic data confirmed. {live_pct:.1f}% of calls hit the real API, ratios show real variation, evidence saved to traffic_audit_log.json.")

    export_path = export_audit_log("traffic_audit_log.json")
    print(f"\nExported complete audit log to: {export_path}")
    print("=" * 80)

    return exit_code


if __name__ == "__main__":
    sys.exit(run_verification())
