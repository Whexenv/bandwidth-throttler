import os
import time
import threading
from collections import deque
import requests
from core.utils import extract_filename

class DownloadEngine:
    """
    HTTP/HTTPS Downloader with Bandwidth Throttling,
    Pause/Resume, Cancellation, and Real-Time Telemetry.
    """

    STATE_IDLE = "IDLE"
    STATE_CONNECTING = "CONNECTING"
    STATE_DOWNLOADING = "DOWNLOADING"
    STATE_PAUSED = "PAUSED"
    STATE_COMPLETED = "COMPLETED"
    STATE_CANCELLED = "CANCELLED"
    STATE_ERROR = "ERROR"

    def __init__(self):
        self.url = ""
        self.save_dir = ""
        self.custom_filename = ""
        self.rate_limit_bytes = 0  # 0 or negative means unlimited

        self.state = self.STATE_IDLE
        self._thread = None
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()

        # Telemetry
        self.total_bytes = 0
        self.downloaded_bytes = 0
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.current_speed = 0.0
        self.average_speed = 0.0
        self.eta_seconds = 0.0

        # Sliding window for instantaneous speed measurement (last 1.0s)
        self._speed_window = deque()
        self._speed_window_lock = threading.Lock()

        # Callbacks
        self.on_progress = None
        self.on_status_change = None
        self.on_complete = None
        self.on_error = None

    def set_rate_limit(self, bytes_per_sec: float):
        """Dynamically update the maximum download speed limit in bytes/sec."""
        self.rate_limit_bytes = max(0.0, float(bytes_per_sec))

    def start(self, url: str, save_dir: str, filename: str = "", rate_limit_bytes: float = 0.0):
        """Start downloading in a dedicated worker thread."""
        if self.state in [self.STATE_DOWNLOADING, self.STATE_CONNECTING]:
            return False

        self.url = url.strip()
        self.save_dir = save_dir
        self.custom_filename = filename.strip()
        self.rate_limit_bytes = max(0.0, float(rate_limit_bytes))

        self._cancel_event.clear()
        self._pause_event.clear()
        self._speed_window.clear()
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.current_speed = 0.0
        self.average_speed = 0.0
        self.eta_seconds = 0.0

        self._set_state(self.STATE_CONNECTING, "Bağlantı kuruluyor...")

        self._thread = threading.Thread(target=self._run_download, daemon=True)
        self._thread.start()
        return True

    def pause(self):
        """Pause the ongoing download."""
        if self.state == self.STATE_DOWNLOADING:
            self._pause_event.set()
            self._set_state(self.STATE_PAUSED, "İndirme duraklatıldı.")

    def resume(self):
        """Resume the paused download."""
        if self.state == self.STATE_PAUSED:
            self._pause_event.clear()
            self._set_state(self.STATE_DOWNLOADING, "İndiriliyor...")

    def cancel(self):
        """Cancel the download."""
        if self.state in [self.STATE_DOWNLOADING, self.STATE_CONNECTING, self.STATE_PAUSED]:
            self._cancel_event.set()
            self._pause_event.clear()
            self._set_state(self.STATE_CANCELLED, "İndirme iptal edildi.")

    def _set_state(self, state: str, message: str = ""):
        self.state = state
        if self.on_status_change:
            self.on_status_change(state, message)

    def _calc_chunk_size(self) -> int:
        """Calculate dynamic chunk size for smooth throttling and low latency."""
        limit = self.rate_limit_bytes
        if limit <= 0:
            return 64 * 1024  # 64 KB default for unlimited
        # Chunk size to achieve ~10-20 iterations per second
        chunk = int(limit / 15)
        # Clamp chunk between 1 KB and 64 KB
        return max(1024, min(64 * 1024, chunk))

    def _run_download(self):
        dest_filepath = None
        session = requests.Session()
        try:
            # Send HTTP GET with stream=True
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) BandwidthThrottler/1.0'
            }
            response = session.get(self.url, stream=True, timeout=15, headers=headers)
            response.raise_for_status()

            # Determine file size
            content_length = response.headers.get('Content-Length')
            if content_length and content_length.isdigit():
                self.total_bytes = int(content_length)
            else:
                self.total_bytes = 0

            # Determine destination filename and path
            filename = self.custom_filename or extract_filename(self.url, response.headers)
            os.makedirs(self.save_dir, exist_ok=True)
            dest_filepath = os.path.join(self.save_dir, filename)

            # Avoid accidental file overwrite with auto-numbering if needed
            base, ext = os.path.splitext(dest_filepath)
            counter = 1
            while os.path.exists(dest_filepath):
                dest_filepath = f"{base}_{counter}{ext}"
                counter += 1

            self._set_state(self.STATE_DOWNLOADING, f"İndiriliyor: {os.path.basename(dest_filepath)}")
            self.start_time = time.perf_counter()
            last_ui_update_time = time.perf_counter()

            with open(dest_filepath, 'wb') as f:
                while True:
                    # Check cancellation
                    if self._cancel_event.is_set():
                        break

                    # Check pause
                    if self._pause_event.is_set():
                        # Clear speed telemetry while paused
                        with self._speed_window_lock:
                            self._speed_window.clear()
                        self.current_speed = 0.0
                        self._trigger_progress()
                        while self._pause_event.is_set():
                            if self._cancel_event.is_set():
                                break
                            time.sleep(0.1)
                        if self._cancel_event.is_set():
                            break

                    chunk_size = self._calc_chunk_size()
                    loop_start = time.perf_counter()

                    # Read raw chunk from stream
                    chunk = response.raw.read(chunk_size)
                    if not chunk:
                        # Reached End-of-Stream
                        break

                    chunk_len = len(chunk)
                    f.write(chunk)
                    self.downloaded_bytes += chunk_len
                    read_elapsed = time.perf_counter() - loop_start

                    # Record chunk in sliding speed telemetry window
                    now = time.perf_counter()
                    with self._speed_window_lock:
                        self._speed_window.append((now, chunk_len))
                        # Keep only data from the last 1.0 second
                        cutoff = now - 1.0
                        while self._speed_window and self._speed_window[0][0] < cutoff:
                            self._speed_window.popleft()

                    # Bandwidth Throttling Logic (time.sleep calculation)
                    limit = self.rate_limit_bytes
                    if limit > 0:
                        expected_duration = chunk_len / limit
                        sleep_time = expected_duration - read_elapsed
                        if sleep_time > 0:
                            # Sleep in tiny slices to quickly react to pause/cancel/limit adjustments
                            sleep_end = time.perf_counter() + sleep_time
                            while time.perf_counter() < sleep_end:
                                if self._cancel_event.is_set() or self._pause_event.is_set():
                                    break
                                remaining_sleep = sleep_end - time.perf_counter()
                                if remaining_sleep > 0:
                                    time.sleep(min(0.015, remaining_sleep))

                    # Update statistics for UI periodically (every ~80ms)
                    if (now - last_ui_update_time) >= 0.08:
                        self._update_metrics(now)
                        self._trigger_progress()
                        last_ui_update_time = now

            # Post-download handling
            if self._cancel_event.is_set():
                # Cleanup partially downloaded file
                try:
                    if dest_filepath and os.path.exists(dest_filepath):
                        os.remove(dest_filepath)
                except Exception:
                    pass
                self._set_state(self.STATE_CANCELLED, "İndirme iptal edildi.")
            else:
                self.current_speed = 0.0
                self._update_metrics(time.perf_counter())
                self._trigger_progress()
                self._set_state(self.STATE_COMPLETED, "İndirme tamamlandı!")
                if self.on_complete:
                    self.on_complete(dest_filepath)

        except Exception as e:
            # Handle download errors cleanly
            if dest_filepath and os.path.exists(dest_filepath):
                try:
                    os.remove(dest_filepath)
                except Exception:
                    pass
            self.current_speed = 0.0
            error_msg = f"Hata: {str(e)}"
            self._set_state(self.STATE_ERROR, error_msg)
            if self.on_error:
                self.on_error(error_msg)
        finally:
            session.close()

    def _update_metrics(self, now: float):
        """Compute instantaneous speed, average speed, and estimated time remaining."""
        # Instantaneous speed from sliding window
        with self._speed_window_lock:
            if len(self._speed_window) >= 2:
                time_span = self._speed_window[-1][0] - self._speed_window[0][0]
                total_bytes_window = sum(b for _, b in self._speed_window)
                if time_span > 0.05:
                    self.current_speed = total_bytes_window / time_span
                else:
                    self.current_speed = float(total_bytes_window)
            elif len(self._speed_window) == 1:
                self.current_speed = float(self._speed_window[0][1])
            else:
                self.current_speed = 0.0

        # Overall elapsed & average speed
        if self.start_time > 0:
            self.elapsed_time = now - self.start_time
            if self.elapsed_time > 0.1:
                self.average_speed = self.downloaded_bytes / self.elapsed_time
            else:
                self.average_speed = self.current_speed

        # ETA calculation
        if self.total_bytes > 0 and self.current_speed > 100:
            remaining_bytes = max(0, self.total_bytes - self.downloaded_bytes)
            self.eta_seconds = remaining_bytes / self.current_speed
        elif self.total_bytes > 0 and self.average_speed > 100:
            remaining_bytes = max(0, self.total_bytes - self.downloaded_bytes)
            self.eta_seconds = remaining_bytes / self.average_speed
        else:
            self.eta_seconds = float('inf')

    def _trigger_progress(self):
        if not self.on_progress:
            return
        percent = 0.0
        if self.total_bytes > 0:
            percent = min(100.0, (self.downloaded_bytes / self.total_bytes) * 100.0)

        metrics = {
            "downloaded": self.downloaded_bytes,
            "total": self.total_bytes,
            "percent": percent,
            "speed": self.current_speed,
            "avg_speed": self.average_speed,
            "eta": self.eta_seconds,
            "elapsed": self.elapsed_time,
            "target_limit": self.rate_limit_bytes,
            "state": self.state
        }
        self.on_progress(metrics)

