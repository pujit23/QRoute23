"""
traffic_provider.py
Live Traffic Provider using TomTom Flow Segment Data API.
Provides non-blocking, cached, and rate-limited traffic-aware utilities for QPSO routing.
"""
import os
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, List, Optional
import requests
import numpy as np

# In-memory traffic cache: (round(lat, 3), round(lon, 3)) -> (timestamp, result_dict)
_TRAFFIC_CACHE: Dict[Tuple[float, float], Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 180

# Rate limiter: max 40 requests per 60 seconds process-wide
_RATE_LIMIT_MAX_CALLS = 40
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_CALL_TIMESTAMPS: List[float] = []

TOMTOM_API_KEY: Optional[str] = None

# In-memory diagnostic audit log for truthful traffic source attribution
_audit_log: List[Dict[str, Any]] = []

_FALLBACK_TRAFFIC = {
    'current_speed_kmh': None,
    'free_flow_speed_kmh': None,
    'ratio': 1.0,
    'confidence': 0.0
}


def _log_traffic_call(lat: Any, lon: Any, source: str, result: Dict[str, Any]) -> None:
    """Safely append a diagnostic entry to _audit_log without ever raising."""
    try:
        try:
            iso_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            iso_ts = ""
        
        try:
            lat_f = round(float(lat), 4)
            lon_f = round(float(lon), 4)
        except Exception:
            lat_f, lon_f = 0.0, 0.0

        _audit_log.append({
            'timestamp': iso_ts,
            'lat': lat_f,
            'lon': lon_f,
            'source': source,
            'ratio': result.get('ratio', 1.0),
            'confidence': result.get('confidence', 0.0)
        })
    except Exception:
        pass


def get_audit_log() -> List[Dict[str, Any]]:
    """Returns a copy of _audit_log (list of dicts), most recent last."""
    return [dict(entry) for entry in _audit_log]


def get_audit_summary() -> Dict[str, Any]:
    """
    Returns a dict:
    {
      'total_calls': int,
      'live_api_calls': int,
      'cache_hits': int,
      'fallback_calls': int,
      'live_data_pct': float (live_api_calls / total_calls * 100, or 0 if total_calls is 0),
      'first_call': timestamp or None,
      'last_call': timestamp or None
    }
    Pure computation over _audit_log, no I/O.
    """
    total = len(_audit_log)
    live_count = sum(1 for entry in _audit_log if entry.get('source') == 'live_api')
    cache_count = sum(1 for entry in _audit_log if entry.get('source') == 'cache')
    fallback_count = sum(1 for entry in _audit_log if entry.get('source') == 'fallback')
    pct = (live_count / total * 100.0) if total > 0 else 0.0
    first_ts = _audit_log[0].get('timestamp') if total > 0 else None
    last_ts = _audit_log[-1].get('timestamp') if total > 0 else None

    return {
        'total_calls': total,
        'live_api_calls': live_count,
        'cache_hits': cache_count,
        'fallback_calls': fallback_count,
        'live_data_pct': pct,
        'first_call': first_ts,
        'last_call': last_ts
    }


def export_audit_log(output_path: str = 'traffic_audit_log.json') -> str:
    """
    Writes get_audit_log() as pretty JSON to output_path. Returns the path.
    This file is your evidence artifact — a real, timestamped, honest record
    of every traffic call made and where its data actually came from.
    """
    try:
        log_data = get_audit_log()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2)
    except Exception:
        pass
    return output_path


def clear_audit_log() -> None:
    """Clears the in-memory audit log."""
    global _audit_log
    _audit_log.clear()


def _get_tomtom_key() -> Optional[str]:
    """
    Retrieve TomTom API key from environment variable or optional config without importing streamlit.
    """
    global TOMTOM_API_KEY
    if TOMTOM_API_KEY:
        return TOMTOM_API_KEY
    key = os.environ.get("TOMTOM_API_KEY")
    if not key:
        # Check config.py if present without mutating
        try:
            import config
            key = getattr(config, "TOMTOM_API_KEY", None)
        except Exception:
            key = None
            
    # Check secrets file if accessible without streamlit dependency
    if not key:
        try:
            secrets_path = os.path.join(".streamlit", "secrets.toml")
            if os.path.exists(secrets_path):
                with open(secrets_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("TOMTOM_API_KEY"):
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                key = parts[1].strip().strip('"').strip("'")
                                break
        except Exception:
            pass

    # Check .env file if accessible
    if not key:
        try:
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            if not os.path.exists(env_path):
                env_path = ".env"
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_s = line.strip()
                        if line_s.startswith("TOMTOM_API_KEY"):
                            parts = line_s.split("=", 1)
                            if len(parts) == 2:
                                candidate = parts[1].strip().strip('"').strip("'")
                                if candidate and candidate != "your_tomtom_api_key_here":
                                    key = candidate
                                    break
        except Exception:
            pass
            
    return key


def _check_rate_limit(now: float) -> bool:
    """
    Returns True if a new API request is allowed under the rate limit, False otherwise.
    Prunes timestamps older than the sliding window.
    """
    global _CALL_TIMESTAMPS
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    _CALL_TIMESTAMPS = [ts for ts in _CALL_TIMESTAMPS if ts > cutoff]
    
    if len(_CALL_TIMESTAMPS) >= _RATE_LIMIT_MAX_CALLS:
        return False
    return True


def get_traffic_flow(lat: float, lon: float) -> Dict[str, Any]:
    """
    Calls TomTom Traffic Flow Segment Data API:
    GET https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json
        ?point={lat},{lon}&key={TOMTOM_API_KEY}

    Returns dict: {
        'current_speed_kmh': float or None,
        'free_flow_speed_kmh': float or None,
        'ratio': current/free_flow (clamped to [0.15, 1.0]),
        'confidence': float (from API response, default 0.5 if missing)
    }

    On ANY failure (network error, timeout >3s, non-200, missing key,
    malformed JSON): returns fallback dict — NEVER raises, NEVER blocks the caller.
    """
    try:
        lat_rounded = round(float(lat), 3)
        lon_rounded = round(float(lon), 3)
    except (ValueError, TypeError):
        fallback_res = dict(_FALLBACK_TRAFFIC)
        _log_traffic_call(lat, lon, 'fallback', fallback_res)
        return fallback_res

    cache_key = (lat_rounded, lon_rounded)
    now = time.time()

    # Check cache first
    if cache_key in _TRAFFIC_CACHE:
        ts, cached_val = _TRAFFIC_CACHE[cache_key]
        if now - ts < _CACHE_TTL_SECONDS:
            cached_res = dict(cached_val)
            _log_traffic_call(lat, lon, 'cache', cached_res)
            return cached_res

    # Check API key
    api_key = _get_tomtom_key()
    if not api_key:
        fallback_res = dict(_FALLBACK_TRAFFIC)
        _log_traffic_call(lat, lon, 'fallback', fallback_res)
        return fallback_res

    # Check rate limit
    if not _check_rate_limit(now):
        # Rate limit reached; return fallback without blocking/sleeping
        fallback_res = dict(_FALLBACK_TRAFFIC)
        _log_traffic_call(lat, lon, 'fallback', fallback_res)
        return fallback_res

    # Record API call timestamp
    _CALL_TIMESTAMPS.append(now)

    url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
    params = {
        "point": f"{lat},{lon}",
        "key": api_key
    }

    try:
        response = requests.get(url, params=params, timeout=3.0)
        if response.status_code == 200:
            data = response.json().get("flowSegmentData", {})
            current_speed = data.get("currentSpeed")
            free_flow_speed = data.get("freeFlowSpeed")
            conf_val = data.get("confidence")
            confidence = float(conf_val) if conf_val is not None else 0.5

            if current_speed is not None and free_flow_speed is not None and float(free_flow_speed) > 0:
                curr_spd = float(current_speed)
                ff_spd = float(free_flow_speed)
                raw_ratio = curr_spd / ff_spd
                clamped_ratio = float(min(1.0, max(0.15, raw_ratio)))
                result = {
                    'current_speed_kmh': curr_spd,
                    'free_flow_speed_kmh': ff_spd,
                    'ratio': clamped_ratio,
                    'confidence': confidence
                }
                _TRAFFIC_CACHE[cache_key] = (now, result)
                _log_traffic_call(lat, lon, 'live_api', result)
                return result
    except Exception:
        pass

    fallback_res = dict(_FALLBACK_TRAFFIC)
    _log_traffic_call(lat, lon, 'fallback', fallback_res)
    return fallback_res


def edge_midpoint(from_coords: Tuple[float, float], to_coords: Tuple[float, float]) -> Tuple[float, float]:
    """Returns ((lat1+lat2)/2, (lon1+lon2)/2). Pure function, no I/O."""
    try:
        return ((float(from_coords[0]) + float(to_coords[0])) / 2.0,
                (float(from_coords[1]) + float(to_coords[1])) / 2.0)
    except Exception:
        return (0.0, 0.0)


def get_edge_traffic(coord_a: Tuple[float, float], coord_b: Tuple[float, float]) -> Dict[str, Any]:
    """
    Samples traffic at the midpoint of the straight line between coord_a and
    coord_b (lat, lon tuples) using get_traffic_flow(). This is a proxy for
    the road segment — acceptable approximation, no real map-matching required.
    Returns the same dict shape as get_traffic_flow.
    """
    try:
        mid_lat, mid_lon = edge_midpoint(coord_a, coord_b)
        return get_traffic_flow(mid_lat, mid_lon)
    except Exception:
        return dict(_FALLBACK_TRAFFIC)



def classify_congestion(ratio: float) -> str:
    """
    Pure function, no I/O. Buckets a speed ratio into a label:
      ratio >= 0.80  -> 'low'
      0.50 <= ratio < 0.80 -> 'medium'
      ratio < 0.50   -> 'high'
    Returns the string label.
    """
    try:
        r = float(ratio)
    except (ValueError, TypeError):
        return 'low'

    if r >= 0.80:
        return 'low'
    elif r >= 0.50:
        return 'medium'
    else:
        return 'high'


def build_traffic_adjusted_matrix(
    nodes: List[Dict[str, Any]],
    dist_matrix_km: np.ndarray,
    time_matrix_hours: np.ndarray
) -> np.ndarray:
    """
    Args: nodes (list of node dicts with 'coords'), and the two matrices from
    app.build_matrices(nodes).
    For every edge (i, j) with i != j:
        edge_traffic = get_edge_traffic(nodes[i]['coords'], nodes[j]['coords'])
        adjusted_time[i][j] = time_matrix_hours[i][j] / edge_traffic['ratio']
    Returns a NEW numpy array. Does NOT mutate time_matrix_hours in place
    (existing callers may hold a reference to the original).
    Diagonal stays 0. Symmetric edges may get different ratios in each
    direction — that's fine and realistic, do not force symmetry.
    """
    n = len(nodes)
    adjusted_time = np.copy(time_matrix_hours)

    for i in range(n):
        for j in range(n):
            if i != j:
                traffic = get_edge_traffic(nodes[i]['coords'], nodes[j]['coords'])
                ratio = traffic.get('ratio', 1.0)
                if ratio and ratio > 0:
                    adjusted_time[i, j] = time_matrix_hours[i, j] / ratio

    return adjusted_time


def annotate_route_traffic(route_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Args: route_nodes — a list of node dicts in visiting order (one vehicle's
    route, depot included), same format app.py already produces.
    For each consecutive pair (route_nodes[k], route_nodes[k+1]):
        fetch get_edge_traffic on their coords
    Returns: list of dicts, one per edge, each:
        {
          'from': node name (str),
          'to': node name (str),
          'from_coords': (lat, lon),
          'to_coords': (lat, lon),
          'ratio': float,
          'level': 'low' | 'medium' | 'high'  (via classify_congestion)
        }
    This is the structure the mapping step consumes.
    """
    segments = []
    if not route_nodes or len(route_nodes) < 2:
        return segments

    for k in range(len(route_nodes) - 1):
        n1 = route_nodes[k]
        n2 = route_nodes[k + 1]
        c1 = n1.get('coords', (0.0, 0.0))
        c2 = n2.get('coords', (0.0, 0.0))

        traffic = get_edge_traffic(c1, c2)
        ratio = float(traffic.get('ratio', 1.0))
        level = classify_congestion(ratio)

        segments.append({
            'from': str(n1.get('name', f"Stop {k}")),
            'to': str(n2.get('name', f"Stop {k + 1}")),
            'from_coords': c1,
            'to_coords': c2,
            'ratio': ratio,
            'level': level
        })

    return segments
