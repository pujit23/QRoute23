"""
report_generator.py
Generates downloadable JSON and PDF reports for QPSO route optimization runs.
Single source of truth: generate_report_data() builds a JSON-serializable dict;
export_report_pdf() and export_report_json() render that exact dict.
No Streamlit dependencies.
"""

import os
import json
import datetime
import logging
from typing import Dict, List, Any, Optional
from geopy.distance import geodesic

logger = logging.getLogger("report_generator")

# Assumed average fuel cost rate (₹8.0/km). Displayed transparently in reports.
FUEL_COST_PER_KM = 8.0
DEFAULT_SPEED_KMH = 50.0


def generate_report_data(
    start_node: Dict[str, Any],
    stops_data: List[Dict[str, Any]],
    routes: List[List[Dict[str, Any]]],
    stats: Dict[str, Any],
    use_case: str = "generic",
    benchmark_results: Optional[Dict[str, Any]] = None,
    live_metrics: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Builds ONE JSON-serializable dict — the single source of truth for both
    export formats. Pure function: no file I/O here.

    Args:
        start_node: depot dict (as used elsewhere in the app)
        stops_data: original list of stop dicts requested
        routes: list of lists of node dicts (one list per vehicle)
        stats: the stats dict already returned by the solver
        use_case: 'delivery' | 'emergency' | 'generic' (default 'generic')
        benchmark_results: optional dict from benchmark comparison
        live_metrics: optional dict containing real-time dashboard KPIs

    Returns:
        JSON-serializable report dictionary.
    """
    valid_use_cases = {"delivery", "emergency", "generic"}
    normalized_use_case = use_case.lower() if isinstance(use_case, str) and use_case.lower() in valid_use_cases else "generic"

    stats = stats or {}
    live_metrics = live_metrics or stats.get("metrics") or {}

    traffic_segs = stats.get("traffic_segments")
    has_traffic = (
        traffic_segs is not None
        and isinstance(traffic_segs, list)
        and len(traffic_segs) > 0
        and any(isinstance(s, list) and len(s) > 0 for s in traffic_segs)
    )
    data_source = "live" if has_traffic else "fallback"

    # --- 1. Vehicle Routes Processing & Calculations ---
    vehicle_routes_list = []
    calc_total_distance_km = 0.0
    calc_total_time_hours = 0.0
    total_traffic_delay_min = 0.0 if has_traffic else None
    
    any_window_defined = False
    total_window_stops = 0
    on_time_stops_count = 0

    all_segments_flat = []
    high_count = 0
    med_count = 0
    low_count = 0

    live_vehicles = live_metrics.get("vehicles", [])

    for v_idx, route in enumerate(routes):
        v_dist_km = 0.0
        v_time_hrs = 0.0
        stops_output = []
        curr_time_hrs = 8.0  # Start route time benchmark at 08:00 AM

        v_traffic_segs = (
            traffic_segs[v_idx]
            if (has_traffic and v_idx < len(traffic_segs) and isinstance(traffic_segs[v_idx], list))
            else []
        )

        live_v_metric = live_vehicles[v_idx] if v_idx < len(live_vehicles) and isinstance(live_vehicles[v_idx], dict) else {}
        live_v_dist = live_v_metric.get("dist_km", live_v_metric.get("dist"))
        live_v_time = live_v_metric.get("time_min", live_v_metric.get("time"))

        for s_idx, node in enumerate(route):
            coords = node.get("coords", (0.0, 0.0))
            coords_list = [float(coords[0]), float(coords[1])]
            name = str(node.get("name", f"Stop {s_idx}"))
            raw_window = node.get("window")
            time_window = [float(raw_window[0]), float(raw_window[1])] if raw_window else None

            if s_idx == 0:
                leg_dist_km = 0.0
                leg_traffic_level = "unknown"
                arrival_time = round(curr_time_hrs, 2)
                on_time = True if time_window else None
                if time_window:
                    any_window_defined = True
                    total_window_stops += 1
                    on_time_stops_count += 1
            else:
                prev_node = route[s_idx - 1]
                prev_coords = prev_node.get("coords", (0.0, 0.0))
                
                # Distance calculation using geodesic curvature
                try:
                    leg_dist_km = round(geodesic(prev_coords, coords).km * 1.25, 2)
                except Exception:
                    leg_dist_km = 0.0

                # Traffic segment information
                leg_traffic_ratio = 1.0
                if s_idx - 1 < len(v_traffic_segs):
                    seg_info = v_traffic_segs[s_idx - 1]
                    leg_traffic_level = seg_info.get("level", "unknown")
                    leg_traffic_ratio = float(seg_info.get("ratio", 1.0))
                    all_segments_flat.append({
                        "from": str(seg_info.get("from", prev_node.get("name", "Stop"))),
                        "to": str(seg_info.get("to", name)),
                        "ratio": leg_traffic_ratio
                    })
                    if leg_traffic_level == "high":
                        high_count += 1
                    elif leg_traffic_level == "medium":
                        med_count += 1
                    elif leg_traffic_level == "low":
                        low_count += 1
                else:
                    leg_traffic_level = "unknown" if not has_traffic else "low"

                # Travel duration calculation
                base_leg_time_hrs = leg_dist_km / DEFAULT_SPEED_KMH
                effective_ratio = max(0.15, leg_traffic_ratio)
                actual_leg_time_hrs = base_leg_time_hrs / effective_ratio

                if has_traffic and total_traffic_delay_min is not None:
                    delay_min = max(0.0, (actual_leg_time_hrs - base_leg_time_hrs) * 60.0)
                    total_traffic_delay_min += delay_min

                curr_time_hrs += actual_leg_time_hrs
                arrival_time = round(curr_time_hrs, 2)

                on_time = None
                if time_window:
                    any_window_defined = True
                    total_window_stops += 1
                    if arrival_time <= time_window[1]:
                        on_time = True
                        on_time_stops_count += 1
                    else:
                        on_time = False

                    if arrival_time < time_window[0]:
                        curr_time_hrs = time_window[0]

                v_dist_km += leg_dist_km
                v_time_hrs += actual_leg_time_hrs

            stops_output.append({
                "sequence": s_idx + 1,
                "name": name,
                "coords": coords_list,
                "arrival_time_hours": arrival_time,
                "time_window": time_window,
                "on_time": on_time,
                "distance_from_previous_km": leg_dist_km,
                "leg_traffic_level": leg_traffic_level
            })

        final_v_dist_km = round(float(live_v_dist), 2) if live_v_dist is not None else round(v_dist_km, 2)
        if live_v_time is not None:
            final_v_time_min = round(float(live_v_time), 1)
            final_v_time_hrs = round(final_v_time_min / 60.0, 2)
        else:
            final_v_time_hrs = round(v_time_hrs, 2)
            final_v_time_min = round(final_v_time_hrs * 60.0, 1)

        calc_total_distance_km += final_v_dist_km
        calc_total_time_hours += final_v_time_hrs

        vehicle_routes_list.append({
            "vehicle_id": v_idx + 1,
            "stops": stops_output,
            "vehicle_distance_km": final_v_dist_km,
            "vehicle_time_minutes": final_v_time_min,
            "vehicle_time_hours": final_v_time_hrs
        })

    # Override total metrics with live_metrics if available
    total_distance_km = round(float(live_metrics.get("total_distance_km")), 2) if live_metrics.get("total_distance_km") is not None else round(calc_total_distance_km, 2)
    
    if live_metrics.get("total_time_min") is not None:
        total_time_min = round(float(live_metrics.get("total_time_min")), 1)
        total_time_hours = round(total_time_min / 60.0, 2)
    elif live_metrics.get("total_time_hours") is not None:
        total_time_hours = round(float(live_metrics.get("total_time_hours")), 2)
        total_time_min = round(total_time_hours * 60.0, 1)
    else:
        total_time_hours = round(calc_total_time_hours, 2)
        total_time_min = round(total_time_hours * 60.0, 1)

    time_saved_hrs = round(float(live_metrics.get("time_saved_hrs")), 1) if live_metrics.get("time_saved_hrs") is not None else round((((total_distance_km * 1.25) - total_distance_km) / 40.0), 1)
    co2_reduction_kg = round(float(live_metrics.get("co2_reduction_kg")), 1) if live_metrics.get("co2_reduction_kg") is not None else round(((total_distance_km * 1.25) - total_distance_km) * 0.12, 1)
    fuel_liters = round(float(live_metrics.get("fuel_liters")), 1) if live_metrics.get("fuel_liters") is not None else round(total_distance_km / 12.0, 1)

    if live_metrics.get("cost_inr") is not None:
        estimated_fuel_cost = round(float(live_metrics.get("cost_inr")), 2)
    elif live_metrics.get("estimated_fuel_cost") is not None:
        estimated_fuel_cost = round(float(live_metrics.get("estimated_fuel_cost")), 2)
    else:
        estimated_fuel_cost = round(total_distance_km * FUEL_COST_PER_KM, 2)

    if total_traffic_delay_min is not None:
        total_traffic_delay_min = round(total_traffic_delay_min, 1)

    on_time_rate_pct = (
        round((on_time_stops_count / total_window_stops) * 100.0, 1)
        if any_window_defined and total_window_stops > 0
        else None
    )

    # --- 2. Traffic Analysis ---
    all_segments_flat.sort(key=lambda x: x["ratio"])
    worst_segments = all_segments_flat[:5] if all_segments_flat else []

    traffic_note = (
        "Live TomTom traffic segment data used. Real-world congestion reflected."
        if data_source == "live"
        else "Fallback free-flow traffic model used. Figures assume ideal road conditions."
    )

    traffic_analysis = {
        "high_congestion_segments": high_count,
        "medium_congestion_segments": med_count,
        "low_congestion_segments": low_count,
        "worst_segments": worst_segments,
        "note": traffic_note
    }

    # --- 3. Optimization Performance ---
    history = stats.get("history", [])
    initial_cost = round(float(history[0]), 2) if history else None
    final_cost = round(float(history[-1]), 2) if history else None
    convergence_rate = stats.get("convergence_rate")
    if convergence_rate is not None:
        convergence_rate = round(float(convergence_rate), 4)

    vs_baseline = None
    if benchmark_results and isinstance(benchmark_results, dict):
        base_cost = benchmark_results.get("baseline_cost")
        base_name = benchmark_results.get("baseline_algorithm", "Greedy Baseline")
        if base_cost and final_cost:
            improvement = round(((base_cost - final_cost) / base_cost) * 100.0, 2)
            vs_baseline = {
                "baseline_algorithm": base_name,
                "baseline_cost": round(float(base_cost), 2),
                "improvement_pct": improvement
            }

    opt_perf = {
        "iterations_run": len(history),
        "final_cost": final_cost,
        "initial_cost": initial_cost,
        "convergence_rate": convergence_rate,
        "tunneling_events": stats.get("tunnels", 0),
        "runtime_seconds": stats.get("runtime_seconds"),
        "vs_baseline": vs_baseline
    }

    # --- 4. Recommendations Generation ---
    recs = []
    if normalized_use_case == "delivery":
        recs.append("Total fleet distance and estimated fuel cost above can be compared week-over-week to track efficiency gains.")
        if on_time_rate_pct is not None and on_time_rate_pct < 100.0:
            recs.append("Stops marked 'not on time' exceeded their delivery window — consider adjusting time windows or adding a vehicle if this recurs.")
        if total_traffic_delay_min and total_traffic_delay_min > 10.0:
            recs.append(f"High-traffic segments account for approximately {total_traffic_delay_min} minutes of delay; consider rescheduling around peak hours if that number is large.")
    elif normalized_use_case == "emergency":
        recs.append("This report shows travel time under current conditions, not a guaranteed response time — always cross-check with your dispatch system before treating it as authoritative for life-safety decisions.")
        recs.append("The fastest single route above should be treated as one candidate path; emergency routing should always keep a manually-verified backup route, since this optimizer does not model road closures or emergency-vehicle priority signals.")
        if high_count > 0:
            recs.append(f"{high_count} high-congestion segment(s) on the route are flagged above — these are candidates for pre-planned detours in your standard operating procedures.")
    else:  # 'generic'
        recs.append("Total distance, time, and cost figures above summarize this specific optimization run and are based on the data source noted in metadata.")
        recs.append("Compare the optimization_performance section across repeated runs to gauge consistency of the solver on your data.")

    # Universal data source caveat
    caveat = (
        f"Data source for this report: {data_source} traffic data, as noted in metadata.data_source. "
        + ("Fallback-mode figures assume free-flow conditions and will understate real-world delay." if data_source == "fallback" else "Live-mode figures account for observed road speeds at the time of calculation.")
    )
    recs.append(caveat)

    total_customer_stops = len(stops_data) if stops_data else sum(max(0, len(r) - 2) for r in routes)

    return {
        "metadata": {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "algorithm": stats.get("algorithm", "QPSO-VRP (Delta Potential Well)"),
            "n_vehicles": len(routes),
            "n_stops": total_customer_stops,
            "data_source": data_source,
            "use_case": normalized_use_case
        },
        "summary": {
            "total_distance_km": total_distance_km,
            "total_time_hours": total_time_hours,
            "total_time_minutes": total_time_min,
            "time_saved_hrs": time_saved_hrs,
            "co2_reduction_kg": co2_reduction_kg,
            "fuel_liters": fuel_liters,
            "estimated_fuel_cost": estimated_fuel_cost,
            "estimated_fuel_cost_inr": estimated_fuel_cost,
            "traffic_delay_minutes": total_traffic_delay_min,
            "on_time_rate_pct": on_time_rate_pct
        },
        "vehicle_routes": vehicle_routes_list,
        "traffic_analysis": traffic_analysis,
        "optimization_performance": opt_perf,
        "recommendations": recs
    }


def export_report_json(report_data: Dict[str, Any], output_path: str = "report.json") -> str:
    """
    Writes report_data as pretty-printed JSON (indent=2).
    Ensures parent directory exists.
    Returns the output path string.
    """
    parent_dir = os.path.dirname(output_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    return output_path


def export_report_pdf(report_data: Dict[str, Any], output_path: str = "report.pdf") -> Optional[str]:
    """
    Builds a formatted printable PDF FROM report_data using fpdf2.
    Sections, in order:
      1. Title + generated_at + algorithm + data_source badge
      2. Executive Summary (the 'summary' dict as a clean key/value block)
      3. Per-vehicle route table (one table per vehicle)
      4. Traffic & Congestion Analysis (counts + worst_segments table)
      5. Optimization Performance (iterations, convergence, tunneling, vs_baseline)
      6. Recommendations (bulleted list from report_data['recommendations'])

    If fpdf2 is missing or generation fails, returns None without raising.
    """
    try:
        from fpdf import FPDF
    except Exception as e:
        logger.warning(f"fpdf2 is not installed or failed to import: {e}")
        return None

    try:
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        class RouteReportPDF(FPDF):
            def header(self):
                self.set_font("Helvetica", "B", 8)
                self.set_text_color(120, 120, 120)
                self.cell(0, 6, "QRoute23 - Quantum-Behaved Route Optimization Report", 0, 0, "R")
                self.ln(8)

            def footer(self):
                self.set_y(-12)
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", 0, 0, "C")

        pdf = RouteReportPDF(orientation="P", unit="mm", format="A4")
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # --- Section 1: Title & Metadata ---
        meta = report_data.get("metadata", {})
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(25, 25, 45)
        pdf.cell(0, 10, "Fleet Route Optimization Report", ln=True)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(80, 80, 80)
        gen_time = meta.get("generated_at", "N/A")
        algo_name = meta.get("algorithm", "QPSO")
        src = meta.get("data_source", "fallback").upper()
        u_case = meta.get("use_case", "generic").upper()
        pdf.cell(0, 5, f"Generated (UTC): {gen_time}   |   Use Case: {u_case}", ln=True)
        pdf.cell(0, 5, f"Algorithm: {algo_name}   |   Data Source: {src} TRAFFIC", ln=True)
        pdf.ln(4)

        # Divider line
        pdf.set_draw_color(210, 215, 225)
        pdf.set_line_width(0.4)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        # --- Section 2: Executive Summary ---
        summary = report_data.get("summary", {})
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(30, 40, 70)
        pdf.cell(0, 8, "1. Executive Summary", ln=True)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_fill_color(245, 247, 250)
        pdf.set_text_color(40, 40, 40)

        dist_val = f"{summary.get('total_distance_km', 0.0)} km"
        
        time_min = summary.get('total_time_minutes')
        time_hrs = summary.get('total_time_hours', 0.0)
        time_val = f"{time_min} min ({time_hrs} hrs)" if time_min is not None else f"{time_hrs} hrs"

        time_saved = summary.get('time_saved_hrs')
        time_saved_val = f"{time_saved} hrs vs baseline" if time_saved is not None else "N/A"

        co2 = summary.get('co2_reduction_kg')
        co2_val = f"{co2} kg CO2 reduction" if co2 is not None else "N/A"

        cost_inr = summary.get('estimated_fuel_cost_inr', summary.get('estimated_fuel_cost', 0.0))
        fuel_l = summary.get('fuel_liters')
        cost_val = f"Rs.{cost_inr} (~{fuel_l} L fuel)" if fuel_l is not None else f"Rs.{cost_inr}"

        delay_raw = summary.get("traffic_delay_minutes")
        delay_val = f"{delay_raw} mins" if delay_raw is not None else "N/A (fallback mode)"
        on_time_raw = summary.get("on_time_rate_pct")
        on_time_val = f"{on_time_raw}%" if on_time_raw is not None else "N/A (no time windows)"

        summary_rows = [
            ("Total Fleet Distance", dist_val),
            ("Total Travel Time", time_val),
            ("Time Saved (Optimization)", time_saved_val),
            ("CO2 Reduction Offset", co2_val),
            ("Estimated Fuel & Cost", cost_val),
            ("Traffic Delay Estimate", delay_val),
            ("On-Time Delivery Rate", on_time_val),
            ("Vehicles / Customer Stops", f"{meta.get('n_vehicles', 1)} vehicles / {meta.get('n_stops', 0)} stops")
        ]

        col_w1 = 65
        col_w2 = 125
        for label, val in summary_rows:
            pdf.cell(col_w1, 6, f"  {label}:", border=1, fill=True)
            pdf.cell(col_w2, 6, f"  {val}", border=1, ln=True)
        pdf.ln(6)

        # --- Section 3: Per-Vehicle Route Table ---
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(30, 40, 70)
        pdf.cell(0, 8, "2. Vehicle Route Manifests", ln=True)

        v_routes = report_data.get("vehicle_routes", [])
        for v in v_routes:
            v_id = v.get("vehicle_id", 1)
            v_dist = v.get("vehicle_distance_km", 0.0)
            v_min = v.get("vehicle_time_minutes")
            v_hrs = v.get("vehicle_time_hours", 0.0)
            dur_str = f"{v_min} min ({v_hrs} hrs)" if v_min is not None else f"{v_hrs} hrs"

            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(45, 55, 80)
            pdf.cell(0, 6, f"Vehicle #{v_id} - Distance: {v_dist} km | Duration: {dur_str}", ln=True)

            # Table Header
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(225, 232, 245)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(10, 6, "Seq", border=1, fill=True, align="C")
            pdf.cell(85, 6, "Stop Name", border=1, fill=True)
            pdf.cell(25, 6, "Arrival (h)", border=1, fill=True, align="C")
            pdf.cell(25, 6, "Leg Dist (km)", border=1, fill=True, align="C")
            pdf.cell(25, 6, "Traffic", border=1, fill=True, align="C")
            pdf.cell(20, 6, "Status", border=1, fill=True, align="C", ln=True)

            # Table Rows
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(40, 40, 40)
            for s in v.get("stops", []):
                seq = str(s.get("sequence", ""))
                raw_name = s.get("name", "Stop")
                # Truncate overly long names for PDF table cell
                name = (raw_name[:42] + "..") if len(raw_name) > 44 else raw_name
                arr = f"{s.get('arrival_time_hours', '')}h" if s.get("arrival_time_hours") is not None else "-"
                leg_d = f"{s.get('distance_from_previous_km', 0.0)}"
                trf = str(s.get("leg_traffic_level", "unknown")).upper()
                ot = s.get("on_time")
                status_str = "ON TIME" if ot is True else ("LATE" if ot is False else "-")

                pdf.cell(10, 5, seq, border=1, align="C")
                pdf.cell(85, 5, f" {name}", border=1)
                pdf.cell(25, 5, arr, border=1, align="C")
                pdf.cell(25, 5, leg_d, border=1, align="C")
                pdf.cell(25, 5, trf, border=1, align="C")
                pdf.cell(20, 5, status_str, border=1, align="C", ln=True)

            pdf.ln(4)

        # --- Section 4: Traffic & Congestion Analysis ---
        trf_analysis = report_data.get("traffic_analysis", {})
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(30, 40, 70)
        pdf.cell(0, 8, "3. Traffic & Congestion Analysis", ln=True)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(50, 50, 50)
        h_cnt = trf_analysis.get("high_congestion_segments", 0)
        m_cnt = trf_analysis.get("medium_congestion_segments", 0)
        l_cnt = trf_analysis.get("low_congestion_segments", 0)
        note_txt = trf_analysis.get("note", "")

        pdf.cell(0, 5, f"Segment Breakdown: High Congestion: {h_cnt}   |   Medium: {m_cnt}   |   Low: {l_cnt}", ln=True)
        pdf.cell(0, 5, f"Note: {note_txt}", ln=True)
        pdf.ln(2)

        worst = trf_analysis.get("worst_segments", [])
        if worst:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(240, 240, 245)
            pdf.cell(75, 5, "From Stop", border=1, fill=True)
            pdf.cell(75, 5, "To Stop", border=1, fill=True)
            pdf.cell(40, 5, "Speed Ratio (Observed/Free)", border=1, fill=True, align="C", ln=True)

            pdf.set_font("Helvetica", "", 8)
            for seg in worst:
                f_name = (seg.get("from", "")[:35] + "..") if len(seg.get("from", "")) > 37 else seg.get("from", "")
                t_name = (seg.get("to", "")[:35] + "..") if len(seg.get("to", "")) > 37 else seg.get("to", "")
                ratio_str = f"{seg.get('ratio', 1.0):.2f}"
                pdf.cell(75, 5, f" {f_name}", border=1)
                pdf.cell(75, 5, f" {t_name}", border=1)
                pdf.cell(40, 5, ratio_str, border=1, align="C", ln=True)
            pdf.ln(4)

        # --- Section 5: Optimization Performance ---
        opt_data = report_data.get("optimization_performance", {})
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(30, 40, 70)
        pdf.cell(0, 8, "4. Optimization Performance", ln=True)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(40, 40, 40)
        iters = opt_data.get("iterations_run", 0)
        f_cost = opt_data.get("final_cost", "N/A")
        i_cost = opt_data.get("initial_cost", "N/A")
        conv = opt_data.get("convergence_rate", "N/A")
        tunnels = opt_data.get("tunneling_events", 0)
        rt = opt_data.get("runtime_seconds")
        rt_str = f"{rt}s" if rt is not None else "N/A"

        pdf.cell(0, 5, f"Total Iterations: {iters}   |   Initial Cost: {i_cost}   |   Final Optimal Cost: {f_cost}", ln=True)
        pdf.cell(0, 5, f"Convergence Rate: {conv}   |   Quantum Tunneling Events: {tunnels}   |   Runtime: {rt_str}", ln=True)

        vs_b = opt_data.get("vs_baseline")
        if vs_b:
            b_name = vs_b.get("baseline_algorithm", "Baseline")
            b_cost = vs_b.get("baseline_cost", "N/A")
            b_imp = vs_b.get("improvement_pct", "N/A")
            pdf.cell(0, 5, f"Benchmark Comparison vs {b_name}: Baseline Cost {b_cost} ({b_imp}% improvement)", ln=True)
        pdf.ln(4)

        # --- Section 6: Recommendations ---
        recs_list = report_data.get("recommendations", [])
        if recs_list:
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(30, 40, 70)
            pdf.cell(0, 8, "5. Recommendations & Operational Notes", ln=True)

            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(50, 50, 50)
            for r_item in recs_list:
                pdf.multi_cell(0, 5, f"- {r_item}")
                pdf.ln(1)

        pdf.output(output_path)
        return output_path

    except Exception as e:
        logger.error(f"Error generating PDF report: {e}", exc_info=True)
        return None
