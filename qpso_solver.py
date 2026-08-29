"""
qpso_solver.py
Quantum-Behaved Particle Swarm Optimization (QPSO) VRP Solver.
Supports single & multi-vehicle routing, classical PSO, greedy baseline, and live traffic cost adjustment.
"""
import time
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.cluster import KMeans
import app

try:
    from traffic_provider import build_traffic_adjusted_matrix, annotate_route_traffic
    _TRAFFIC_AVAILABLE = True
except Exception:
    _TRAFFIC_AVAILABLE = False


def _spv_decode(position_vector: np.ndarray, n_stops: int) -> List[int]:
    """
    Discretizes continuous particle position to stop sequence using Smallest Position Value (SPV).
    Returns list of 0-indexed node indices starting with depot 0.
    """
    if n_stops <= 0:
        return [0]
    # argsort gives 0-indexed order of stops (1..n_stops)
    order = np.argsort(position_vector)
    return [0] + [int(idx + 1) for idx in order]


def _run_qpso_single(
    nodes: List[Dict[str, Any]],
    dist_matrix: np.ndarray,
    time_matrix: np.ndarray,
    q_params: Optional[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Core QPSO single-vehicle optimization using Delta-Potential Well model.
    """
    n = len(nodes)
    if n <= 1:
        return nodes, {
            "history": [0.0],
            "tunnels": 0,
            "final_temp": 0.0,
            "algorithm": "QPSO-VRP (Delta Potential Well)",
            "convergence_rate": 0.0
        }
    if n == 2:
        return nodes, {
            "history": [float(app.calculate_energy([0, 1], dist_matrix, time_matrix, nodes))],
            "tunnels": 0,
            "final_temp": 0.0,
            "algorithm": "QPSO-VRP (Delta Potential Well)",
            "convergence_rate": 0.0
        }

    n_stops = n - 1
    params = q_params or {}
    swarm_size = int(params.get("swarm_size", params.get("particles", 30)))
    max_iter = int(params.get("iter", params.get("max_iter", 300)))
    beta_start = float(params.get("beta_start", 1.0))
    beta_end = float(params.get("beta_end", 0.5))

    # Initialize continuous positions in [0, 1]^n_stops
    X = np.random.uniform(0.0, 1.0, (swarm_size, n_stops))
    pbest = np.copy(X)
    pbest_energy = np.zeros(swarm_size)

    for i in range(swarm_size):
        route_idx = _spv_decode(X[i], n_stops)
        pbest_energy[i] = app.calculate_energy(route_idx, dist_matrix, time_matrix, nodes)

    gbest_idx = int(np.argmin(pbest_energy))
    gbest = np.copy(pbest[gbest_idx])
    gbest_energy = float(pbest_energy[gbest_idx])

    history = [gbest_energy]
    tunneling_events = 0
    start_time = time.time()

    for it in range(max_iter):
        # Linear annealing of contraction-expansion coefficient
        beta = beta_start - (beta_start - beta_end) * (it / max(max_iter, 1))
        mbest = np.mean(pbest, axis=0)

        for i in range(swarm_size):
            phi = np.random.uniform(0.0, 1.0, n_stops)
            p_i = phi * pbest[i] + (1.0 - phi) * gbest

            u = np.random.uniform(0.0, 1.0, n_stops)
            u = np.maximum(u, 1e-10)
            sign = np.where(np.random.rand(n_stops) < 0.5, 1.0, -1.0)

            # Delta-potential well update
            X[i] = p_i + sign * beta * np.abs(mbest - X[i]) * np.log(1.0 / u)

            route_idx = _spv_decode(X[i], n_stops)
            curr_energy = app.calculate_energy(route_idx, dist_matrix, time_matrix, nodes)

            # Quantum tunneling exploration event
            if curr_energy > pbest_energy[i] and np.random.rand() < 0.05:
                tunneling_events += 1

            if curr_energy < pbest_energy[i]:
                pbest[i] = np.copy(X[i])
                pbest_energy[i] = curr_energy
                if curr_energy < gbest_energy:
                    gbest = np.copy(X[i])
                    gbest_energy = float(curr_energy)

        history.append(gbest_energy)

    best_indices = _spv_decode(gbest, n_stops)
    best_nodes = [nodes[idx] for idx in best_indices]

    initial_e = history[0] if history else gbest_energy
    final_e = history[-1] if history else gbest_energy
    convergence_rate = float((initial_e - final_e) / max(initial_e, 1e-6)) if initial_e > 0 else 0.0
    final_temp = float(gbest_energy / max(n, 1))

    stats = {
        "history": history,
        "tunnels": tunneling_events,
        "final_temp": final_temp,
        "algorithm": "QPSO-VRP (Delta Potential Well)",
        "convergence_rate": convergence_rate,
        "execution_time_ms": (time.time() - start_time) * 1000.0
    }
    return best_nodes, stats


def solve_qpso_vrp(
    start_node: Dict[str, Any],
    stops_data: List[Dict[str, Any]],
    n_vehicles: int = 1,
    q_params: Optional[Dict[str, Any]] = None
) -> Tuple[List[List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Solves Vehicle Routing Problem using Quantum-Behaved PSO.
    Supports single or multi-vehicle routing and optional live traffic adjustment.

    Args:
        start_node: Dict with 'name' and 'coords': (lat, lon)
        stops_data: List of stop dicts with 'name', 'coords', and optional 'window'
        n_vehicles: Number of vehicles
        q_params: Optional dictionary of parameters (including 'use_live_traffic')

    Returns:
        (routes, stats)
        - routes: List of vehicle routes (each route is a list of node dicts starting with start_node)
        - stats: Telemetry dictionary including history, tunnels, final_temp, algorithm,
                 convergence_rate, and traffic_segments (if use_live_traffic=True)
    """
    nodes = [start_node] + stops_data
    n = len(nodes)

    if n <= 1:
        use_traffic = bool(q_params and q_params.get('use_live_traffic'))
        return [[start_node]], {
            "history": [0.0],
            "tunnels": 0,
            "final_temp": 0.0,
            "algorithm": "QPSO-VRP (Delta Potential Well)",
            "convergence_rate": 0.0,
            "traffic_segments": [] if (use_traffic and _TRAFFIC_AVAILABLE) else None
        }

    total_final_dist = 0.0
    total_final_time = 0.0

    # Handle Multi-Vehicle via Clustering
    if n_vehicles > 1 and len(stops_data) > 1:
        k = min(n_vehicles, len(stops_data))
        coords = np.array([[s['coords'][0], s['coords'][1]] for s in stops_data])
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit(coords)

        clusters: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(k)}
        for idx, label in enumerate(kmeans.labels_):
            clusters[int(label)].append(stops_data[idx])

        routes = []
        combined_history = []
        total_tunnels = 0
        total_temp = 0.0

        for label, sub_stops in clusters.items():
            if not sub_stops:
                continue
            sub_nodes = [start_node] + sub_stops
            dist_matrix_km, time_matrix_hours = app.build_matrices(sub_nodes)

            if q_params and q_params.get('use_live_traffic') and _TRAFFIC_AVAILABLE:
                try:
                    time_matrix_hours = build_traffic_adjusted_matrix(sub_nodes, dist_matrix_km, time_matrix_hours)
                except Exception:
                    pass

            sub_route, sub_stats = _run_qpso_single(sub_nodes, dist_matrix_km, time_matrix_hours, q_params=q_params)
            routes.append(sub_route)
            total_tunnels += sub_stats.get("tunnels", 0)
            total_temp += sub_stats.get("final_temp", 0.0)
            combined_history.extend(sub_stats.get("history", []))

            sub_map = {id(n): idx for idx, n in enumerate(sub_nodes)}
            for k_idx in range(len(sub_route) - 1):
                u = sub_map.get(id(sub_route[k_idx]))
                v = sub_map.get(id(sub_route[k_idx + 1]))
                if u is not None and v is not None:
                    total_final_dist += float(dist_matrix_km[u, v])
                    total_final_time += float(time_matrix_hours[u, v])

        stats: Dict[str, Any] = {
            "history": combined_history,
            "tunnels": total_tunnels,
            "final_temp": total_temp / max(len(routes), 1),
            "algorithm": "QPSO-VRP (Delta Potential Well)",
            "convergence_rate": float(
                (combined_history[0] - combined_history[-1]) / max(combined_history[0], 1e-6)
            ) if combined_history else 0.0,
            "final_distance_km": round(float(total_final_dist), 2),
            "final_time_hours": round(float(total_final_time), 4)
        }
    else:
        # Single Vehicle Route
        dist_matrix_km, time_matrix_hours = app.build_matrices(nodes)

        if q_params and q_params.get('use_live_traffic') and _TRAFFIC_AVAILABLE:
            try:
                time_matrix_hours = build_traffic_adjusted_matrix(nodes, dist_matrix_km, time_matrix_hours)
            except Exception:
                pass  # fall back silently to the static matrix already computed

        best_nodes, stats = _run_qpso_single(nodes, dist_matrix_km, time_matrix_hours, q_params=q_params)
        routes = [best_nodes]

        node_map = {id(n): idx for idx, n in enumerate(nodes)}
        for k_idx in range(len(best_nodes) - 1):
            u = node_map.get(id(best_nodes[k_idx]))
            v = node_map.get(id(best_nodes[k_idx + 1]))
            if u is not None and v is not None:
                total_final_dist += float(dist_matrix_km[u, v])
                total_final_time += float(time_matrix_hours[u, v])

        stats["final_distance_km"] = round(float(total_final_dist), 2)
        stats["final_time_hours"] = round(float(total_final_time), 4)

    # Annotate traffic segments if live traffic requested and available
    if q_params and q_params.get('use_live_traffic') and _TRAFFIC_AVAILABLE:
        try:
            stats['traffic_segments'] = [annotate_route_traffic(r) for r in routes]
        except Exception:
            stats['traffic_segments'] = None
    else:
        stats['traffic_segments'] = None

    return routes, stats


def solve_classical_pso_vrp(
    start_node: Dict[str, Any],
    stops_data: List[Dict[str, Any]],
    n_vehicles: int = 1,
    q_params: Optional[Dict[str, Any]] = None
) -> Tuple[List[List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Classical Velocity-based Particle Swarm Optimization (PSO) baseline solver.
    """
    nodes = [start_node] + stops_data
    n = len(nodes)

    if n <= 1:
        return [[start_node]], {
            "history": [0.0],
            "tunnels": 0,
            "final_temp": 0.0,
            "algorithm": "Classical PSO (v-based)",
            "convergence_rate": 0.0,
            "traffic_segments": None
        }

    # Clustering for multi-vehicle
    if n_vehicles > 1 and len(stops_data) > 1:
        k = min(n_vehicles, len(stops_data))
        coords = np.array([[s['coords'][0], s['coords'][1]] for s in stops_data])
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit(coords)
        clusters: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(k)}
        for idx, label in enumerate(kmeans.labels_):
            clusters[int(label)].append(stops_data[idx])
        routes = []
        combined_history = []
        for label, sub_stops in clusters.items():
            if not sub_stops:
                continue
            sub_nodes = [start_node] + sub_stops
            sub_res, sub_st = solve_classical_pso_vrp(start_node, sub_stops, n_vehicles=1, q_params=q_params)
            routes.append(sub_res[0])
            combined_history.extend(sub_st.get("history", []))

        stats: Dict[str, Any] = {
            "history": combined_history,
            "tunnels": 0,
            "final_temp": 0.0,
            "algorithm": "Classical PSO (v-based)",
            "convergence_rate": float(
                (combined_history[0] - combined_history[-1]) / max(combined_history[0], 1e-6)
            ) if combined_history else 0.0
        }
        if q_params and q_params.get('use_live_traffic') and _TRAFFIC_AVAILABLE:
            stats['traffic_segments'] = [annotate_route_traffic(r) for r in routes]
        else:
            stats['traffic_segments'] = None
        return routes, stats

    dist_matrix_km, time_matrix_hours = app.build_matrices(nodes)

    if q_params and q_params.get('use_live_traffic') and _TRAFFIC_AVAILABLE:
        try:
            time_matrix_hours = build_traffic_adjusted_matrix(nodes, dist_matrix_km, time_matrix_hours)
        except Exception:
            pass

    n_stops = n - 1
    params = q_params or {}
    M = int(params.get("swarm_size", 30))
    max_iter = int(params.get("max_iter", params.get("iter", 300)))
    w = 0.7
    c1, c2 = 1.49, 1.49

    X = np.random.uniform(0.0, 1.0, (M, n_stops))
    V = np.random.uniform(-0.1, 0.1, (M, n_stops))
    pbest = np.copy(X)
    pbest_fit = np.zeros(M)

    for i in range(M):
        r_idx = _spv_decode(X[i], n_stops)
        pbest_fit[i] = app.calculate_energy(r_idx, dist_matrix_km, time_matrix_hours, nodes)

    gbest_idx = int(np.argmin(pbest_fit))
    gbest = np.copy(pbest[gbest_idx])
    gbest_fit = float(pbest_fit[gbest_idx])

    history = [gbest_fit]

    for it in range(max_iter):
        r1 = np.random.uniform(0.0, 1.0, (M, n_stops))
        r2 = np.random.uniform(0.0, 1.0, (M, n_stops))
        V = w * V + c1 * r1 * (pbest - X) + c2 * r2 * (gbest - X)
        X = X + V

        for i in range(M):
            r_idx = _spv_decode(X[i], n_stops)
            fit = app.calculate_energy(r_idx, dist_matrix_km, time_matrix_hours, nodes)
            if fit < pbest_fit[i]:
                pbest[i] = np.copy(X[i])
                pbest_fit[i] = fit
                if fit < gbest_fit:
                    gbest = np.copy(X[i])
                    gbest_fit = float(fit)

        history.append(gbest_fit)

    best_indices = _spv_decode(gbest, n_stops)
    best_nodes = [nodes[idx] for idx in best_indices]
    routes = [best_nodes]

    stats = {
        "history": history,
        "tunnels": 0,
        "final_temp": float(gbest_fit / max(n, 1)),
        "algorithm": "Classical PSO (v-based)",
        "convergence_rate": float((history[0] - history[-1]) / max(history[0], 1e-6)) if history else 0.0
    }

    if q_params and q_params.get('use_live_traffic') and _TRAFFIC_AVAILABLE:
        try:
            stats['traffic_segments'] = [annotate_route_traffic(r) for r in routes]
        except Exception:
            stats['traffic_segments'] = None
    else:
        stats['traffic_segments'] = None

    return routes, stats


def solve_greedy_vrp(
    start_node: Dict[str, Any],
    stops_data: List[Dict[str, Any]],
    n_vehicles: int = 1,
    q_params: Optional[Dict[str, Any]] = None
) -> Tuple[List[List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Greedy Nearest Neighbor heuristic baseline solver.
    """
    nodes = [start_node] + stops_data
    n = len(nodes)

    if n <= 1:
        return [[start_node]], {
            "history": [0.0],
            "tunnels": 0,
            "final_temp": 0.0,
            "algorithm": "Greedy Nearest Neighbor",
            "convergence_rate": 0.0,
            "traffic_segments": None
        }

    # Clustering for multi-vehicle
    if n_vehicles > 1 and len(stops_data) > 1:
        k = min(n_vehicles, len(stops_data))
        coords = np.array([[s['coords'][0], s['coords'][1]] for s in stops_data])
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit(coords)
        clusters: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(k)}
        for idx, label in enumerate(kmeans.labels_):
            clusters[int(label)].append(stops_data[idx])
        routes = []
        for label, sub_stops in clusters.items():
            if not sub_stops:
                continue
            sub_res, _ = solve_greedy_vrp(start_node, sub_stops, n_vehicles=1, q_params=q_params)
            routes.append(sub_res[0])

        stats: Dict[str, Any] = {
            "history": [0.0],
            "tunnels": 0,
            "final_temp": 0.0,
            "algorithm": "Greedy Nearest Neighbor",
            "convergence_rate": 0.0
        }
        if q_params and q_params.get('use_live_traffic') and _TRAFFIC_AVAILABLE:
            stats['traffic_segments'] = [annotate_route_traffic(r) for r in routes]
        else:
            stats['traffic_segments'] = None
        return routes, stats

    dist_matrix_km, time_matrix_hours = app.build_matrices(nodes)

    if q_params and q_params.get('use_live_traffic') and _TRAFFIC_AVAILABLE:
        try:
            time_matrix_hours = build_traffic_adjusted_matrix(nodes, dist_matrix_km, time_matrix_hours)
        except Exception:
            pass

    unvisited = set(range(1, n))
    curr_route = [0]
    curr_node = 0
    while unvisited:
        next_node = min(unvisited, key=lambda x: dist_matrix_km[curr_node][x])
        curr_route.append(next_node)
        unvisited.remove(next_node)
        curr_node = next_node

    energy = app.calculate_energy(curr_route, dist_matrix_km, time_matrix_hours, nodes)
    best_nodes = [nodes[idx] for idx in curr_route]
    routes = [best_nodes]

    stats = {
        "history": [float(energy)],
        "tunnels": 0,
        "final_temp": float(energy / max(n, 1)),
        "algorithm": "Greedy Nearest Neighbor",
        "convergence_rate": 0.0
    }

    if q_params and q_params.get('use_live_traffic') and _TRAFFIC_AVAILABLE:
        try:
            stats['traffic_segments'] = [annotate_route_traffic(r) for r in routes]
        except Exception:
            stats['traffic_segments'] = None
    else:
        stats['traffic_segments'] = None

    return routes, stats


def run_benchmark(
    start_node: Dict[str, Any],
    stops_data: List[Dict[str, Any]],
    n_vehicles: int = 1,
    q_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Runs multi-algorithm benchmark comparison (QPSO, Classical PSO, Greedy).
    Forwards q_params unchanged.
    """
    qpso_routes, qpso_stats = solve_qpso_vrp(start_node, stops_data, n_vehicles=n_vehicles, q_params=q_params)
    cpso_routes, cpso_stats = solve_classical_pso_vrp(start_node, stops_data, n_vehicles=n_vehicles, q_params=q_params)
    greedy_routes, greedy_stats = solve_greedy_vrp(start_node, stops_data, n_vehicles=n_vehicles, q_params=q_params)

    return {
        "qpso": {
            "routes": qpso_routes,
            "stats": qpso_stats
        },
        "classical_pso": {
            "routes": cpso_routes,
            "stats": cpso_stats
        },
        "greedy": {
            "routes": greedy_routes,
            "stats": greedy_stats
        }
    }
