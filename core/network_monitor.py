import time
import threading
import psutil
from typing import Dict, List, Optional, Set

class ProcessNetworkInfo:
    def __init__(self, name: str):
        self.name: str = name
        self.pids: Set[int] = set()
        self.down_speed: float = 0.0  # Bytes / sec
        self.up_speed: float = 0.0    # Bytes / sec
        self.total_down: int = 0      # Total Bytes
        self.total_up: int = 0        # Total Bytes
        self.connections_count: int = 0
        self.exe_path: str = ""
        self.is_throttled: bool = False
        self.throttle_rate: int = 0   # Bytes / sec

    def to_dict(self):
        return {
            "name": self.name,
            "pids": list(self.pids),
            "pid_display": str(list(self.pids)[0]) if len(self.pids) == 1 else f"{len(self.pids)} süreç",
            "down_speed": self.down_speed,
            "up_speed": self.up_speed,
            "total_down": self.total_down,
            "total_up": self.total_up,
            "connections_count": self.connections_count,
            "exe_path": self.exe_path,
            "is_throttled": self.is_throttled,
            "throttle_rate": self.throttle_rate,
        }


class NetworkMonitor:
    """
    Monitors all active processes and their real-time network traffic / bandwidth usage.
    """

    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # State: pid -> (last_read, last_write, timestamp)
        self._last_pid_io: Dict[int, tuple] = {}
        # Latest snapshot: name -> ProcessNetworkInfo
        self._latest_processes: Dict[str, ProcessNetworkInfo] = {}

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def get_processes(self, query: str = "", only_active_network: bool = False) -> List[dict]:
        with self._lock:
            procs = list(self._latest_processes.values())

        q = query.strip().lower()
        filtered = []
        for p in procs:
            if q and (q not in p.name.lower() and not any(q in str(pid) for pid in p.pids)):
                continue
            if only_active_network and (p.down_speed <= 0 and p.up_speed <= 0 and p.connections_count <= 0):
                continue
            filtered.append(p.to_dict())

        # Sort: first throttled, then highest total speed (down + up), then active connections
        filtered.sort(
            key=lambda x: (
                1 if x["is_throttled"] else 0,
                x["down_speed"] + x["up_speed"],
                x["connections_count"]
            ),
            reverse=True
        )
        return filtered

    def _monitor_loop(self):
        while self.running:
            t_start = time.perf_counter()
            self._update_stats()
            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.2, self.interval - elapsed)
            time.sleep(sleep_time)

    def _update_stats(self):
        now = time.perf_counter()
        
        # 1. Collect active network connections per PID
        net_conn_count: Dict[int, int] = {}
        try:
            for c in psutil.net_connections(kind="inet"):
                if c.pid and c.pid > 0:
                    net_conn_count[c.pid] = net_conn_count.get(c.pid, 0) + 1
        except Exception:
            pass

        # 2. Iterate processes and sample I/O
        current_data: Dict[str, ProcessNetworkInfo] = {}
        new_pid_io = {}

        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            pid = proc.info['pid']
            if pid <= 4:  # Skip System / Idle
                continue

            name = proc.info['name']
            if not name:
                continue
            name_lower = name.lower()

            try:
                io = proc.io_counters()
                r_bytes = io.read_bytes
                w_bytes = io.write_bytes
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            new_pid_io[pid] = (r_bytes, w_bytes, now)

            # Compute delta
            dr = 0.0
            ur = 0.0
            if pid in self._last_pid_io:
                prev_r, prev_w, prev_t = self._last_pid_io[pid]
                dt = now - prev_t
                if dt > 0:
                    dr = max(0.0, (r_bytes - prev_r) / dt)
                    ur = max(0.0, (w_bytes - prev_w) / dt)

            conn_count = net_conn_count.get(pid, 0)

            # Only track if has connections, has active traffic, or significant total transfer
            if conn_count > 0 or dr > 0 or ur > 0 or r_bytes > 500000:
                if name_lower not in current_data:
                    info = ProcessNetworkInfo(name)
                    info.exe_path = proc.info.get('exe') or ""
                    current_data[name_lower] = info
                else:
                    info = current_data[name_lower]

                info.pids.add(pid)
                info.down_speed += dr
                info.up_speed += ur
                info.total_down += r_bytes
                info.total_up += w_bytes
                info.connections_count += conn_count

        self._last_pid_io = new_pid_io

        with self._lock:
            self._latest_processes = current_data

