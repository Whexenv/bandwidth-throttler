import tkinter as tk
from collections import deque
from core.utils import format_speed

class SpeedGraphWidget(tk.Canvas):
    """
    A high-performance, modern real-time canvas chart for visualizing
    download speed history and bandwidth throttle threshold.
    """
    def __init__(self, master, max_points: int = 50, **kwargs):
        # Default modern dark palette
        self.bg_color = kwargs.pop("bg", "#18191c")
        self.grid_color = "#2a2d32"
        self.text_color = "#8a909a"
        self.line_color = "#00d2ff"      # Glowing electric cyan
        self.fill_color = "#003b46"      # Deep cyan translucent base
        self.limit_color = "#ff4d6d"     # Distinct red-pink for throttle limit line

        super().__init__(master, bg=self.bg_color, highlightthickness=0, **kwargs)

        self.max_points = max_points
        self.data_points = deque(maxlen=max_points)
        self.limit_points = deque(maxlen=max_points)

        # Pre-fill with zeros for clean startup graph
        for _ in range(max_points):
            self.data_points.append(0.0)
            self.limit_points.append(0.0)

        self.bind("<Configure>", lambda e: self.redraw())

    def update_theme(self, is_dark: bool):
        """Update colors based on current theme mode."""
        if is_dark:
            self.bg_color = "#18191c"
            self.grid_color = "#2a2d32"
            self.text_color = "#8a909a"
            self.line_color = "#00d2ff"
            self.fill_color = "#0d2b38"
            self.limit_color = "#ff5376"
        else:
            self.bg_color = "#f4f5f8"
            self.grid_color = "#e2e4e9"
            self.text_color = "#60646c"
            self.line_color = "#007acc"
            self.fill_color = "#d6edff"
            self.limit_color = "#d92550"

        self.configure(bg=self.bg_color)
        self.redraw()

    def add_point(self, current_speed: float, target_limit: float = 0.0):
        """Append a new speed data point and refresh the canvas."""
        self.data_points.append(max(0.0, float(current_speed)))
        self.limit_points.append(max(0.0, float(target_limit)))
        self.redraw()

    def reset(self):
        """Reset the chart history."""
        self.data_points.clear()
        self.limit_points.clear()
        for _ in range(self.max_points):
            self.data_points.append(0.0)
            self.limit_points.append(0.0)
        self.redraw()

    def redraw(self):
        """Rerender the entire graph."""
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()

        if width <= 20 or height <= 20:
            return

        # Margins
        padding_left = 65
        padding_right = 20
        padding_top = 20
        padding_bottom = 25

        plot_width = max(10, width - padding_left - padding_right)
        plot_height = max(10, height - padding_top - padding_bottom)

        # Find dynamic Y-axis ceiling
        max_val_data = max(self.data_points) if self.data_points else 0.0
        max_val_limit = max(self.limit_points) if self.limit_points else 0.0
        max_val = max(max_val_data, max_val_limit)

        if max_val < 1024:
            max_val = 50 * 1024  # Default floor 50 KB/s
        else:
            max_val = max_val * 1.25  # Give 25% headroom for aesthetic breathing room

        # Draw horizontal grid lines & Y-axis labels (4 divisions)
        steps = 4
        for i in range(steps + 1):
            y_ratio = i / steps
            y = padding_top + (1.0 - y_ratio) * plot_height
            val_at_y = y_ratio * max_val

            # Grid line
            self.create_line(
                padding_left, y, width - padding_right, y,
                fill=self.grid_color, width=1, dash=(3, 3) if i > 0 and i < steps else None
            )

            # Label
            label_text = format_speed(val_at_y)
            self.create_text(
                padding_left - 8, y,
                text=label_text, anchor="e",
                fill=self.text_color, font=("Segoe UI", 9)
            )

        # Draw bottom axis line
        self.create_line(
            padding_left, padding_top + plot_height,
            width - padding_right, padding_top + plot_height,
            fill=self.grid_color, width=2
        )

        n = len(self.data_points)
        if n < 2:
            return

        x_step = plot_width / (n - 1)

        # Compute point coordinates
        coords = []
        limit_coords = []
        for idx in range(n):
            x = padding_left + idx * x_step
            speed_val = self.data_points[idx]
            y = padding_top + (1.0 - min(1.0, speed_val / max_val)) * plot_height
            coords.append((x, y))

            limit_val = self.limit_points[idx]
            if limit_val > 0:
                ly = padding_top + (1.0 - min(1.0, limit_val / max_val)) * plot_height
                limit_coords.append((x, ly))

        # Under-curve gradient / polygon fill
        if len(coords) >= 2:
            polygon_pts = [coords[0][0], padding_top + plot_height]
            for cx, cy in coords:
                polygon_pts.extend([cx, cy])
            polygon_pts.extend([coords[-1][0], padding_top + plot_height])
            self.create_polygon(polygon_pts, fill=self.fill_color, outline="")

        # Draw speed limit target line (if set)
        if len(limit_coords) >= 2:
            flat_limit = [c for pt in limit_coords for c in pt]
            self.create_line(
                flat_limit, fill=self.limit_color,
                width=1.5, dash=(4, 3)
            )

        # Draw main speed curve
        if len(coords) >= 2:
            flat_coords = [c for pt in coords for c in pt]
            self.create_line(
                flat_coords, fill=self.line_color,
                width=2.5, smooth=True
            )

            # Draw latest point indicator dot
            last_x, last_y = coords[-1]
            self.create_oval(
                last_x - 4, last_y - 4, last_x + 4, last_y + 4,
                fill=self.line_color, outline="#ffffff", width=1.5
            )

        # Chart Legend in the top right
        legend_x = width - padding_right - 10
        legend_y = padding_top - 5

        # Speed Legend
        self.create_text(
            legend_x, legend_y,
            text=f"Anlık: {format_speed(self.data_points[-1])}",
            anchor="se", fill=self.line_color, font=("Segoe UI", 9, "bold")
        )

        current_limit = self.limit_points[-1]
        if current_limit > 0:
            self.create_text(
                legend_x - 140, legend_y,
                text=f"-- Limit: {format_speed(current_limit)}",
                anchor="se", fill=self.limit_color, font=("Segoe UI", 9)
            )

