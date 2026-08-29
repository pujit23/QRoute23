"""
traffic_map.py
Standalone Folium-based visualization and reporting for traffic-aware routes.
Zero streamlit dependencies; renders on standard OpenStreetMap tiles.
"""
from typing import List, Dict, Any, Optional
import folium


def render_traffic_map(
    routes: List[List[Dict[str, Any]]],
    all_traffic_segments: Optional[List[List[Dict[str, Any]]]],
    output_path: str = 'route_traffic_map.html'
) -> str:
    """
    Renders an interactive Folium map of vehicle routes with color-coded traffic congestion.

    Args:
        routes: List of lists of node dicts (one list per vehicle), as returned by solve_qpso_vrp
        all_traffic_segments: The 'traffic_segments' list from stats
                              (one list of edge-dicts per vehicle route) or None
        output_path: Destination file path for the generated HTML map

    Behavior:
    - Centers folium.Map on depot (start_node) coordinates.
    - For each vehicle's route:
        - If all_traffic_segments is provided:
            color = green  if level == 'low'
            color = orange if level == 'medium'
            color = red    if level == 'high'
            weight=5, opacity=0.8
            Adds a highlighted marker at the midpoint of every 'high' congestion edge.
        - If all_traffic_segments is None:
            Renders route in a single neutral color (blue) without crashing.
    - Adds markers at the depot and every stop with popup descriptions.
    - Saves to output_path using map.save().

    Returns:
        The output_path string.
    """
    # 1. Determine Map Center
    center_coords = [40.7128, -74.0060]
    if routes and len(routes) > 0 and len(routes[0]) > 0:
        first_node = routes[0][0]
        if 'coords' in first_node and first_node['coords']:
            center_coords = [first_node['coords'][0], first_node['coords'][1]]

    route_map = folium.Map(location=center_coords, zoom_start=12, tiles="OpenStreetMap")

    level_colors = {
        'low': 'green',
        'medium': 'orange',
        'high': 'red'
    }

    # 2. Draw Edges
    if all_traffic_segments is not None:
        for v_idx, segments in enumerate(all_traffic_segments):
            if not segments:
                continue
            for seg in segments:
                c1 = seg.get('from_coords')
                c2 = seg.get('to_coords')
                if not c1 or not c2:
                    continue
                level = seg.get('level', 'low')
                color = level_colors.get(level, 'green')
                ratio = float(seg.get('ratio', 1.0))
                from_name = seg.get('from', 'Start')
                to_name = seg.get('to', 'End')

                # Draw PolyLine per edge
                folium.PolyLine(
                    locations=[[c1[0], c1[1]], [c2[0], c2[1]]],
                    color=color,
                    weight=5,
                    opacity=0.8,
                    tooltip=f"Vehicle {v_idx + 1}: {from_name} -> {to_name} ({level.upper()} traffic, ratio: {ratio:.2f})"
                ).add_to(route_map)

                # Add Midpoint Highlight for 'high' Congestion
                if level == 'high':
                    mid_lat = (c1[0] + c2[0]) / 2.0
                    mid_lon = (c1[1] + c2[1]) / 2.0
                    pct = int(round(ratio * 100))
                    popup_msg = f"Heavy traffic: {pct}% of free-flow speed ({from_name} -> {to_name})"
                    folium.CircleMarker(
                        location=[mid_lat, mid_lon],
                        radius=7,
                        color="#990000",
                        fill=True,
                        fill_color="red",
                        fill_opacity=0.9,
                        popup=popup_msg,
                        tooltip=popup_msg
                    ).add_to(route_map)
    else:
        # Single neutral color fallback when traffic segments not available
        for v_idx, route in enumerate(routes):
            coords = [[node['coords'][0], node['coords'][1]] for node in route if 'coords' in node and node['coords']]
            if len(coords) > 1:
                folium.PolyLine(
                    locations=coords,
                    color="#3388ff",
                    weight=5,
                    opacity=0.8,
                    tooltip=f"Vehicle {v_idx + 1} Route"
                ).add_to(route_map)

    # 3. Add Stop and Depot Markers
    added_markers = set()
    for route in routes:
        for idx, node in enumerate(route):
            coords = node.get('coords')
            if not coords:
                continue
            marker_key = (round(coords[0], 5), round(coords[1], 5))
            if marker_key in added_markers:
                continue
            added_markers.add(marker_key)

            name = node.get('name', f"Stop {idx}")
            is_depot = (idx == 0)
            icon_color = "red" if is_depot else "blue"
            icon_symbol = "home" if is_depot else "info-sign"

            folium.Marker(
                location=[coords[0], coords[1]],
                popup=name,
                tooltip=name,
                icon=folium.Icon(color=icon_color, icon=icon_symbol)
            ).add_to(route_map)

    # 4. Save HTML Map
    route_map.save(output_path)
    return output_path


def summarize_high_traffic(all_traffic_segments: Optional[List[List[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    """
    Returns a simple list of dicts, one per 'high' congestion edge across all vehicles:
    [{'vehicle': int, 'from': str, 'to': str, 'ratio': float}, ...]
    sorted by ratio ascending (worst congestion first). Empty list if
    all_traffic_segments is None or empty. Pure function, no I/O, no plotting.
    Useful for printing a quick 'worst traffic spots on this route' summary.
    """
    if not all_traffic_segments:
        return []

    high_edges: List[Dict[str, Any]] = []
    for v_idx, segments in enumerate(all_traffic_segments):
        if not segments:
            continue
        for seg in segments:
            if seg.get('level') == 'high':
                high_edges.append({
                    'vehicle': v_idx,
                    'from': str(seg.get('from', '')),
                    'to': str(seg.get('to', '')),
                    'ratio': float(seg.get('ratio', 1.0))
                })

    # Sort ascending by ratio (worst speed reduction first)
    high_edges.sort(key=lambda x: x['ratio'])
    return high_edges
