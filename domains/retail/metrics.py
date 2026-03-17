"""Retail analytics metrics — traffic, dwell time, queues, occupancy.

Processes CV pipeline output (person detection + tracking + zones) and
computes retail-specific metrics from the timeline data.
"""

from collections import defaultdict
import time


class RetailMetrics:
    """Compute retail analytics from CV pipeline tracking data."""

    def __init__(self, capacity: int = 0):
        """
        Args:
            capacity: Max occupancy for the space (0 = no limit/alerts)
        """
        self.capacity = capacity
        self._entry_zone = None
        self._exit_zone = None

    def set_entry_exit_zones(self, entry_zone: str, exit_zone: str | None = None):
        """Define which zones are entry/exit points for traffic counting."""
        self._entry_zone = entry_zone
        self._exit_zone = exit_zone or entry_zone  # Same zone = bidirectional

    def compute_from_timeline(self, timeline: list[dict], zones_defined: list[dict] | None = None) -> dict:
        """Compute all retail metrics from a CV pipeline timeline.

        Args:
            timeline: List of snapshots from CVPipeline.analyze_video()
            zones_defined: Zone definitions for zone-specific analytics

        Returns:
            Dict with traffic, dwell, queue, occupancy, and heatmap data
        """
        if not timeline:
            return self._empty_result()

        # Track person presence across time
        person_first_seen = {}   # track_id → first timestamp
        person_last_seen = {}    # track_id → last timestamp
        person_positions = defaultdict(list)  # track_id → [(timestamp, centroid)]
        person_zones = defaultdict(lambda: defaultdict(float))  # track_id → {zone → total_seconds}

        # Per-timestamp metrics
        occupancy_timeline = []
        zone_occupancy_timeline = defaultdict(list)  # zone → [(timestamp, count)]

        prev_timestamp = None
        prev_zone_people = defaultdict(set)  # zone → set of track_ids

        for snap in timeline:
            ts = snap["timestamp"]
            tracks = snap.get("tracks", {})
            zone_occ = snap.get("zone_occupancy", {})
            dt = (ts - prev_timestamp) if prev_timestamp is not None else 0

            # Track individual people
            for tid, info in tracks.items():
                if tid not in person_first_seen:
                    person_first_seen[tid] = ts
                person_last_seen[tid] = ts
                if info.get("centroid"):
                    person_positions[tid].append((ts, info["centroid"]))

            # Zone dwell time
            current_zone_people = defaultdict(set)
            for zone_name, tids in zone_occ.items():
                for tid in tids:
                    current_zone_people[zone_name].add(tid)
                    if dt > 0 and tid in prev_zone_people.get(zone_name, set()):
                        person_zones[tid][zone_name] += dt

            prev_zone_people = current_zone_people
            prev_timestamp = ts

            # Occupancy at this timestamp
            count = snap.get("person_count", len(tracks))
            occupancy_timeline.append({"timestamp": ts, "count": count})

            for zone_name, tids in zone_occ.items():
                zone_occupancy_timeline[zone_name].append({"timestamp": ts, "count": len(tids)})

        # Compute traffic metrics
        total_duration = timeline[-1]["timestamp"] - timeline[0]["timestamp"] if len(timeline) > 1 else 0
        total_unique = len(person_first_seen)

        # Dwell time per person
        dwell_times = []
        for tid in person_first_seen:
            dwell = person_last_seen[tid] - person_first_seen[tid]
            dwell_times.append(dwell)

        avg_dwell = sum(dwell_times) / len(dwell_times) if dwell_times else 0
        max_dwell = max(dwell_times) if dwell_times else 0
        min_dwell = min(dwell_times) if dwell_times else 0

        # Occupancy stats
        counts = [o["count"] for o in occupancy_timeline]
        avg_occupancy = sum(counts) / len(counts) if counts else 0
        max_occupancy = max(counts) if counts else 0
        peak_times = [o["timestamp"] for o in occupancy_timeline if o["count"] == max_occupancy]

        # Zone dwell summary
        zone_dwell_summary = {}
        for zone_name in set(z for zones in person_zones.values() for z in zones):
            zone_dwells = [person_zones[tid].get(zone_name, 0) for tid in person_zones if person_zones[tid].get(zone_name, 0) > 0]
            if zone_dwells:
                zone_dwell_summary[zone_name] = {
                    "visitors": len(zone_dwells),
                    "avg_dwell_seconds": round(sum(zone_dwells) / len(zone_dwells), 1),
                    "max_dwell_seconds": round(max(zone_dwells), 1),
                    "total_dwell_seconds": round(sum(zone_dwells), 1),
                }

        # Traffic rate (people per minute)
        traffic_rate = (total_unique / (total_duration / 60)) if total_duration > 60 else total_unique

        # Heatmap data (centroid frequency grid)
        heatmap = self._compute_heatmap(person_positions)

        # Queue detection (people in queue zone, if defined)
        queue_metrics = {}
        for zone in (zones_defined or []):
            if zone.get("zone_type") == "entry":
                zone_name = zone["name"]
                if zone_name in zone_occupancy_timeline:
                    queue_counts = [e["count"] for e in zone_occupancy_timeline[zone_name]]
                    queue_metrics[zone_name] = {
                        "avg_queue_length": round(sum(queue_counts) / len(queue_counts), 1),
                        "max_queue_length": max(queue_counts),
                        "samples": len(queue_counts),
                    }

        return {
            "traffic": {
                "total_visitors": total_unique,
                "traffic_rate_per_minute": round(traffic_rate, 1),
                "duration_seconds": round(total_duration, 1),
            },
            "dwell_time": {
                "avg_seconds": round(avg_dwell, 1),
                "max_seconds": round(max_dwell, 1),
                "min_seconds": round(min_dwell, 1),
                "per_person": {tid: round(d, 1) for tid, d in zip(person_first_seen.keys(), dwell_times)},
            },
            "occupancy": {
                "current": counts[-1] if counts else 0,
                "average": round(avg_occupancy, 1),
                "max": max_occupancy,
                "capacity": self.capacity,
                "over_capacity": max_occupancy > self.capacity if self.capacity > 0 else False,
                "peak_timestamps": peak_times[:5],
                "timeline": occupancy_timeline,
            },
            "zones": zone_dwell_summary,
            "zone_timelines": {z: tl for z, tl in zone_occupancy_timeline.items()},
            "queues": queue_metrics,
            "heatmap": heatmap,
        }

    def _compute_heatmap(self, person_positions: dict, grid_size: int = 20) -> dict:
        """Compute a simple grid-based heatmap from centroid positions."""
        if not person_positions:
            return {"grid": [], "grid_size": grid_size}

        # Find bounds
        all_positions = [pos for positions in person_positions.values() for _, pos in positions]
        if not all_positions:
            return {"grid": [], "grid_size": grid_size}

        xs = [p[0] for p in all_positions]
        ys = [p[1] for p in all_positions]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        range_x = max(max_x - min_x, 1)
        range_y = max(max_y - min_y, 1)

        # Build grid
        grid = [[0] * grid_size for _ in range(grid_size)]
        for x, y in all_positions:
            gx = min(grid_size - 1, int((x - min_x) / range_x * (grid_size - 1)))
            gy = min(grid_size - 1, int((y - min_y) / range_y * (grid_size - 1)))
            grid[gy][gx] += 1

        # Normalize to 0-100
        max_val = max(max(row) for row in grid) or 1
        grid = [[round(cell / max_val * 100) for cell in row] for row in grid]

        return {
            "grid": grid,
            "grid_size": grid_size,
            "bounds": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
        }

    def _empty_result(self) -> dict:
        return {
            "traffic": {"total_visitors": 0, "traffic_rate_per_minute": 0, "duration_seconds": 0},
            "dwell_time": {"avg_seconds": 0, "max_seconds": 0, "min_seconds": 0, "per_person": {}},
            "occupancy": {"current": 0, "average": 0, "max": 0, "capacity": self.capacity,
                          "over_capacity": False, "peak_timestamps": [], "timeline": []},
            "zones": {},
            "zone_timelines": {},
            "queues": {},
            "heatmap": {"grid": [], "grid_size": 20},
        }
