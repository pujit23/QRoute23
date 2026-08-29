"""
tests/test_traffic_qpso.py
Comprehensive test suite for Traffic-Aware QPSO-VRP Extension.
"""
import os
import tempfile
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

import traffic_provider
from traffic_provider import (
    get_traffic_flow,
    get_edge_traffic,
    classify_congestion,
    build_traffic_adjusted_matrix,
    annotate_route_traffic
)
import qpso_solver
from qpso_solver import (
    solve_qpso_vrp,
    solve_classical_pso_vrp,
    solve_greedy_vrp,
    run_benchmark
)
import logic
from logic import (
    optimize_route_algo,
    optimize_route_qpso,
    optimize_route_qpso_traffic
)
import traffic_map
from traffic_map import (
    render_traffic_map,
    summarize_high_traffic
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_nodes():
    start = {"name": "Depot NYC", "coords": (40.7488, -73.9854)}
    stops = [
        {"name": "Empire State", "coords": (40.7484, -73.9857), "window": (8.5, 12.0)},
        {"name": "Chrysler Bldg", "coords": (40.7516, -73.9755), "window": (9.0, 14.0)},
        {"name": "Rockefeller", "coords": (40.7587, -73.9787), "window": (10.0, 16.0)},
    ]
    return start, stops


# ── 1. Traffic Provider Tests ────────────────────────────────────────────────

def test_classify_congestion():
    """Verify congestion thresholds: >=0.80 low, 0.50..0.80 medium, <0.50 high."""
    assert classify_congestion(1.0) == "low"
    assert classify_congestion(0.85) == "low"
    assert classify_congestion(0.80) == "low"
    assert classify_congestion(0.79) == "medium"
    assert classify_congestion(0.50) == "medium"
    assert classify_congestion(0.49) == "high"
    assert classify_congestion(0.15) == "high"
    assert classify_congestion(0.0) == "high"
    assert classify_congestion("invalid") == "low"


def test_get_edge_traffic_midpoint():
    """Verify midpoint coordinate calculation in straight-line traffic sampling."""
    coord_a = (40.0, -74.0)
    coord_b = (40.2, -73.8)

    with patch("traffic_provider.get_traffic_flow") as mock_flow:
        mock_flow.return_value = {
            'current_speed_kmh': 30.0,
            'free_flow_speed_kmh': 60.0,
            'ratio': 0.5,
            'confidence': 0.8
        }
        res = get_edge_traffic(coord_a, coord_b)
        mock_flow.assert_called_once_with(40.1, -73.9)
        assert res['ratio'] == 0.5


def test_get_traffic_flow_success():
    """Verify successful TomTom flowSegmentData parsing and ratio clamping."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "flowSegmentData": {
            "currentSpeed": 25,
            "freeFlowSpeed": 50,
            "confidence": 0.9
        }
    }
    with patch("requests.get", return_value=mock_resp), \
         patch("traffic_provider._get_tomtom_key", return_value="dummy_key"), \
         patch.dict("traffic_provider._TRAFFIC_CACHE", {}, clear=True):
        res = get_traffic_flow(40.75, -73.98)
        assert res['current_speed_kmh'] == 25.0
        assert res['free_flow_speed_kmh'] == 50.0
        assert res['ratio'] == 0.5
        assert res['confidence'] == 0.9


def test_get_traffic_flow_clamping_and_fallback():
    """Verify ratio clamping to [0.15, 1.0] and non-crashing fallback on exception."""
    # Extremely low speed -> clamped to 0.15
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "flowSegmentData": {
            "currentSpeed": 1,
            "freeFlowSpeed": 100,
            "confidence": 0.7
        }
    }
    with patch("requests.get", return_value=mock_resp), \
         patch("traffic_provider._get_tomtom_key", return_value="dummy_key"), \
         patch.dict("traffic_provider._TRAFFIC_CACHE", {}, clear=True):
        res = get_traffic_flow(40.75, -73.98)
        assert res['ratio'] == 0.15

    # Network Exception -> Fallback dict without raising
    with patch("requests.get", side_effect=Exception("Network down")), \
         patch("traffic_provider._get_tomtom_key", return_value="dummy_key"), \
         patch.dict("traffic_provider._TRAFFIC_CACHE", {}, clear=True):
        res = get_traffic_flow(40.75, -73.98)
        assert res['current_speed_kmh'] is None
        assert res['free_flow_speed_kmh'] is None
        assert res['ratio'] == 1.0
        assert res['confidence'] == 0.0


def test_traffic_cache_and_rate_limiting():
    """Verify in-memory caching TTL and 40 calls/min rate limit fallback."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "flowSegmentData": {"currentSpeed": 40, "freeFlowSpeed": 50, "confidence": 0.8}
    }

    with patch("requests.get", return_value=mock_resp) as mock_req, \
         patch("traffic_provider._get_tomtom_key", return_value="dummy_key"), \
         patch.dict("traffic_provider._TRAFFIC_CACHE", {}, clear=True):
        # 1. First call triggers HTTP request
        res1 = get_traffic_flow(40.751, -73.981)
        assert mock_req.call_count == 1
        assert res1['ratio'] == 0.8

        # 2. Second call with same coordinates hits cache
        res2 = get_traffic_flow(40.7512, -73.9814) # rounds to same 3 decimals
        assert mock_req.call_count == 1
        assert res2['ratio'] == 0.8

    # Test rate limit
    with patch("traffic_provider._get_tomtom_key", return_value="dummy_key"), \
         patch("traffic_provider._check_rate_limit", return_value=False), \
         patch.dict("traffic_provider._TRAFFIC_CACHE", {}, clear=True):
        res_rl = get_traffic_flow(50.0, 10.0)
        assert res_rl['ratio'] == 1.0
        assert res_rl['current_speed_kmh'] is None


def test_build_traffic_adjusted_matrix():
    """Verify matrix adjustment creates a new array and penalizes congested travel time."""
    nodes = [
        {"name": "A", "coords": (40.70, -74.00)},
        {"name": "B", "coords": (40.75, -73.95)}
    ]
    dist_mat = np.array([[0.0, 10.0], [10.0, 0.0]])
    time_mat = np.array([[0.0, 0.2], [0.2, 0.0]])

    with patch("traffic_provider.get_edge_traffic") as mock_edge:
        mock_edge.return_value = {'ratio': 0.5, 'confidence': 0.9}
        adj_mat = build_traffic_adjusted_matrix(nodes, dist_mat, time_mat)

        # Original matrix must NOT be mutated
        assert time_mat[0, 1] == 0.2
        # Adjusted time should double because ratio is 0.5 (time / 0.5 = time * 2)
        assert np.isclose(adj_mat[0, 1], 0.4)
        assert np.isclose(adj_mat[1, 0], 0.4)
        assert adj_mat[0, 0] == 0.0


def test_annotate_route_traffic():
    """Verify annotate_route_traffic produces edge dictionaries with congestion levels."""
    route_nodes = [
        {"name": "Depot", "coords": (40.70, -74.00)},
        {"name": "Stop 1", "coords": (40.75, -73.95)},
        {"name": "Depot", "coords": (40.70, -74.00)}
    ]
    with patch("traffic_provider.get_edge_traffic") as mock_edge:
        mock_edge.side_effect = [
            {'ratio': 0.4, 'confidence': 0.8}, # High congestion
            {'ratio': 0.9, 'confidence': 0.8}  # Low congestion
        ]
        segments = annotate_route_traffic(route_nodes)
        assert len(segments) == 2
        assert segments[0]['from'] == "Depot"
        assert segments[0]['to'] == "Stop 1"
        assert segments[0]['ratio'] == 0.4
        assert segments[0]['level'] == "high"

        assert segments[1]['from'] == "Stop 1"
        assert segments[1]['to'] == "Depot"
        assert segments[1]['ratio'] == 0.9
        assert segments[1]['level'] == "low"


# ── 2. QPSO Solver Tests ─────────────────────────────────────────────────────

def test_solve_qpso_vrp_without_traffic(sample_nodes):
    """Verify solve_qpso_vrp regression behavior when use_live_traffic=False."""
    start, stops = sample_nodes
    routes, stats = solve_qpso_vrp(start, stops, n_vehicles=1, q_params={"use_live_traffic": False, "iter": 20})

    assert len(routes) == 1
    assert len(routes[0]) == 4  # Start + 3 stops
    assert "history" in stats
    assert "tunnels" in stats
    assert "final_temp" in stats
    assert "algorithm" in stats
    assert "convergence_rate" in stats
    assert stats["traffic_segments"] is None


def test_solve_qpso_vrp_with_traffic(sample_nodes):
    """Verify solve_qpso_vrp populates traffic_segments when use_live_traffic=True."""
    start, stops = sample_nodes
    with patch("traffic_provider.get_edge_traffic", return_value={'ratio': 0.6, 'confidence': 0.8}):
        routes, stats = solve_qpso_vrp(start, stops, n_vehicles=1, q_params={"use_live_traffic": True, "iter": 20})

        assert len(routes) == 1
        assert stats["traffic_segments"] is not None
        assert len(stats["traffic_segments"]) == 1
        # 4 nodes route has 3 consecutive segments
        assert len(stats["traffic_segments"][0]) == 3
        for seg in stats["traffic_segments"][0]:
            assert seg["ratio"] == 0.6
            assert seg["level"] == "medium"


def test_solve_qpso_vrp_offline_fallback(sample_nodes):
    """Verify solve_qpso_vrp succeeds without error when traffic calls fail completely."""
    start, stops = sample_nodes
    with patch("traffic_provider.get_traffic_flow", side_effect=Exception("Offline")):
        routes, stats = solve_qpso_vrp(start, stops, n_vehicles=1, q_params={"use_live_traffic": True, "iter": 20})
        assert len(routes) == 1
        assert len(routes[0]) == 4


def test_solve_qpso_vrp_multi_vehicle(sample_nodes):
    """Verify multi-vehicle fleet partition and route optimization."""
    start, stops = sample_nodes
    routes, stats = solve_qpso_vrp(start, stops, n_vehicles=2, q_params={"iter": 20})
    assert len(routes) == 2
    assert "history" in stats
    assert "final_temp" in stats


def test_solve_classical_and_greedy_vrp(sample_nodes):
    """Verify classical PSO and greedy baseline functions."""
    start, stops = sample_nodes
    cpso_routes, cpso_stats = solve_classical_pso_vrp(start, stops, n_vehicles=1, q_params={"max_iter": 20})
    assert len(cpso_routes) == 1
    assert len(cpso_routes[0]) == 4

    greedy_routes, greedy_stats = solve_greedy_vrp(start, stops, n_vehicles=1)
    assert len(greedy_routes) == 1
    assert len(greedy_routes[0]) == 4


def test_run_benchmark(sample_nodes):
    """Verify run_benchmark compares multiple algorithms."""
    start, stops = sample_nodes
    bench = run_benchmark(start, stops, n_vehicles=1, q_params={"iter": 10, "max_iter": 10})
    assert "qpso" in bench
    assert "classical_pso" in bench
    assert "greedy" in bench


# ── 3. Logic Router Entry Points ─────────────────────────────────────────────

def test_logic_router_functions(sample_nodes):
    """Verify logic.py router functions maintain interface contract."""
    start, stops = sample_nodes

    # 1. optimize_route_algo legacy
    r1, s1 = optimize_route_algo(start, stops, round_trip=True, fleet_size=1)
    assert len(r1) == 1
    assert len(r1[0]) == 5 # Start + 3 stops + return to Start

    # 2. optimize_route_qpso
    r2, s2 = optimize_route_qpso(start, stops, round_trip=True, fleet_size=1, quantum_params={"iter": 20})
    assert len(r2) == 1
    assert len(r2[0]) == 5
    assert r2[0][0]["name"] == r2[0][-1]["name"]

    # 3. optimize_route_qpso_traffic
    with patch("traffic_provider.get_edge_traffic", return_value={'ratio': 0.7, 'confidence': 0.8}):
        r3, s3 = optimize_route_qpso_traffic(start, stops, round_trip=True, fleet_size=1, quantum_params={"iter": 20})
        assert len(r3) == 1
        assert len(r3[0]) == 5
        assert s3["traffic_segments"] is not None


# ── 4. Traffic Map & Summary Tests ───────────────────────────────────────────

def test_summarize_high_traffic():
    """Verify extraction and sorting of high congestion bottlenecks."""
    traffic_segments = [
        [
            {'from': 'Depot', 'to': 'Stop 1', 'ratio': 0.85, 'level': 'low'},
            {'from': 'Stop 1', 'to': 'Stop 2', 'ratio': 0.35, 'level': 'high'},
            {'from': 'Stop 2', 'to': 'Stop 3', 'ratio': 0.20, 'level': 'high'},
        ],
        [
            {'from': 'Depot', 'to': 'Stop 4', 'ratio': 0.45, 'level': 'high'}
        ]
    ]
    summary = summarize_high_traffic(traffic_segments)
    assert len(summary) == 3
    # Worst ratio first: 0.20 < 0.35 < 0.45
    assert summary[0]['ratio'] == 0.20
    assert summary[0]['from'] == 'Stop 2'
    assert summary[0]['vehicle'] == 0

    assert summary[1]['ratio'] == 0.35
    assert summary[2]['ratio'] == 0.45
    assert summary[2]['vehicle'] == 1

    # Empty/None check
    assert summarize_high_traffic(None) == []
    assert summarize_high_traffic([]) == []


def test_render_traffic_map_with_and_without_traffic(sample_nodes):
    """Verify HTML map rendering with traffic segments and fallback mode."""
    start, stops = sample_nodes
    routes = [[start] + stops + [start]]
    segments = [[
        {'from': 'Depot NYC', 'to': 'Empire State', 'from_coords': (40.7488, -73.9854), 'to_coords': (40.7484, -73.9857), 'ratio': 0.3, 'level': 'high'},
        {'from': 'Empire State', 'to': 'Chrysler Bldg', 'from_coords': (40.7484, -73.9857), 'to_coords': (40.7516, -73.9755), 'ratio': 0.6, 'level': 'medium'},
        {'from': 'Chrysler Bldg', 'to': 'Depot NYC', 'from_coords': (40.7516, -73.9755), 'to_coords': (40.7488, -73.9854), 'ratio': 0.9, 'level': 'low'},
    ]]

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. With traffic segments
        map_path_1 = os.path.join(tmpdir, "test_traffic_map.html")
        out1 = render_traffic_map(routes, segments, output_path=map_path_1)
        assert os.path.exists(out1)
        with open(out1, "r", encoding="utf-8") as f:
            html_content = f.read()
            assert "folium" in html_content or "leaflet" in html_content.lower()

        # 2. Without traffic segments (None)
        map_path_2 = os.path.join(tmpdir, "test_no_traffic_map.html")
        out2 = render_traffic_map(routes, None, output_path=map_path_2)
        assert os.path.exists(out2)


# ── 5. Frontend & Edge Midpoint Tests ────────────────────────────────────────

def test_edge_midpoint():
    """Verify edge_midpoint helper computes exact center."""
    from traffic_provider import edge_midpoint
    assert edge_midpoint((40.0, -74.0), (40.2, -73.8)) == (40.1, -73.9)
    assert edge_midpoint((0.0, 0.0), (10.0, 20.0)) == (5.0, 10.0)
    assert edge_midpoint((None, None), (10.0, 20.0)) == (0.0, 0.0)


def test_frontend_render_optimizer_view(sample_nodes):
    """Verify frontend render_optimizer_view runs cleanly with and without traffic_segments."""
    import streamlit as st
    import frontend

    class MockSessionState(dict):
        def __getattr__(self, name):
            return self.get(name)
        def __setattr__(self, name, value):
            self[name] = value

    start, stops = sample_nodes
    coords = [start["coords"]] + [s["coords"] for s in stops]

    mock_opt_route = {
        "coords": coords,
        "routes_geo": [coords],
        "markers": [
            {"vehicle_id": 0, "stop_idx": 0, "coords": coords[0], "name": "Start", "is_last": False},
            {"vehicle_id": 0, "stop_idx": 1, "coords": coords[1], "name": "Stop 1", "is_last": False},
            {"vehicle_id": 0, "stop_idx": 2, "coords": coords[2], "name": "Stop 2", "is_last": False},
            {"vehicle_id": 0, "stop_idx": 3, "coords": coords[3], "name": "End", "is_last": True}
        ]
    }
    mock_metrics = {
        "dist": 25.0,
        "time": 45.0,
        "fuel": 2.1,
        "cost": 200.0,
        "vehicles": [{"id": 1, "dist": 25.0}]
    }

    segments = [[
        {"from": "Start", "to": "Stop 1", "from_coords": coords[0], "to_coords": coords[1], "ratio": 0.35, "level": "high"},
        {"from": "Stop 1", "to": "Stop 2", "from_coords": coords[1], "to_coords": coords[2], "ratio": 0.65, "level": "medium"},
        {"from": "Stop 2", "to": "End", "from_coords": coords[2], "to_coords": coords[3], "ratio": 0.90, "level": "low"},
    ]]

    mock_state = MockSessionState({
        "optimized_route": mock_opt_route,
        "route_metrics": mock_metrics,
        "is_round_trip_active": False
    })

    with patch.object(st, "session_state", mock_state), patch("frontend.st_folium") as mock_st_folium:
        # 1. Default without traffic segments (None)
        frontend.render_optimizer_view()
        assert mock_st_folium.called

        # 2. With traffic segments
        frontend.render_optimizer_view(traffic_segments=segments)
        assert mock_st_folium.call_count == 2

        # 3. With empty traffic segments list
        frontend.render_optimizer_view(traffic_segments=[])
        assert mock_st_folium.call_count == 3


