import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk

from core.network_monitor import NetworkMonitor
from core.qos_manager import QosManager
from core.downloader import DownloadEngine
from core.utils import format_bytes, format_speed, format_time
from ui.speed_graph import SpeedGraphWidget

# Appearance defaults
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class BandwidthLimiterApp(ctk.CTk):
    """
    Main Application Window:
    - Task Manager live process network monitor with click-to-throttle functionality.
    - Direct URL throttled downloader (Tab 2).
    """

    def __init__(self):
        super().__init__()

        self.title("Bandwidth Limiter - Görev Yöneticisi & Hız Kısıtlayıcı")
        self.geometry("1000x820")
        self.minsize(880, 700)

        self._setup_window_branding()

        # Network monitor for Task Manager
        self.monitor = NetworkMonitor(interval=0.8)
        self.monitor.start()

        # QoS limits cache: {app_name_lower: bytes_per_sec}
        self.active_limits = {}
        self._refresh_active_limits()

        # Selection state
        self.selected_app = None

        # Direct Downloader Engine (Tab 2)
        self.download_engine = DownloadEngine()
        self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(self.download_dir):
            self.download_dir = os.getcwd()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._start_live_updater()

    def _on_closing(self):
        try:
            self.monitor.stop()
        except Exception:
            pass
        self.destroy()

    def _setup_window_branding(self):
        try:
            import ctypes
            app_id = "bandwidththrottler.app.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_ico = os.path.join(base_dir, "assets", "icon.ico")
        icon_png = os.path.join(base_dir, "assets", "icon.png")

        if os.path.exists(icon_ico):
            try:
                self.iconbitmap(icon_ico)
            except Exception:
                pass

        if os.path.exists(icon_png):
            try:
                self._app_icon_photo = ImageTk.PhotoImage(file=icon_png)
                self.wm_iconphoto(True, self._app_icon_photo)
            except Exception:
                pass

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Header Frame
        header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("gray90", "#1e2025"))
        header_frame.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        # Left: Icon & Titles
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_png = os.path.join(base_dir, "assets", "icon.png")
        if os.path.exists(icon_png):
            try:
                self._header_icon_img = ctk.CTkImage(
                    light_image=Image.open(icon_png),
                    dark_image=Image.open(icon_png),
                    size=(40, 40)
                )
                icon_lbl = ctk.CTkLabel(title_box, image=self._header_icon_img, text="")
                icon_lbl.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        text_box = ctk.CTkFrame(title_box, fg_color="transparent")
        text_box.pack(side="left", fill="both")

        title_lbl = ctk.CTkLabel(
            text_box, text="Bandwidth Limiter",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            text_box, text="Görev Yöneticisi Ağ Takibi & Uygulama Bazlı Hız Kısıtlayıcı",
            font=ctk.CTkFont(family="Segoe UI", size=12), text_color=("gray40", "gray65")
        )
        subtitle_lbl.pack(anchor="w")

        # Right: Total Live Speed + Admin Badge + Theme Switch
        right_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_box.grid(row=0, column=1, padx=14, pady=10, sticky="e")

        self.lbl_total_live = ctk.CTkLabel(
            right_box, text="⬇ 0.0 KB/s  |  ⬆ 0.0 KB/s",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("#1f6aa5", "#38bdf8")
        )
        self.lbl_total_live.pack(side="left", padx=(0, 15))

        # Admin Badge / Restart Button
        is_admin = QosManager.is_admin()
        if is_admin:
            admin_lbl = ctk.CTkLabel(
                right_box, text="🛡️ Yönetici: Aktif",
                fg_color=("#dcfce7", "#14532d"), text_color=("#15803d", "#4ade80"),
                corner_radius=6, padx=8, pady=4,
                font=ctk.CTkFont(size=12, weight="bold")
            )
            admin_lbl.pack(side="left", padx=(0, 10))
        else:
            admin_btn = ctk.CTkButton(
                right_box, text="🛡️ Yönetici Yetkisi Al",
                width=135, height=28,
                fg_color="#334155", hover_color="#475569",
                command=QosManager.restart_as_admin,
                font=ctk.CTkFont(size=11, weight="bold")
            )
            admin_btn.pack(side="left", padx=(0, 10))

        theme_switch = ctk.CTkSegmentedButton(
            right_box, values=["Karanlık", "Aydınlık"],
            command=self._toggle_theme, width=120, height=28
        )
        theme_switch.set("Karanlık")
        theme_switch.pack(side="left")

        # 2. Main Tab View
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="nsew")

        self.tab_monitor = self.tabview.add("📊 Görev Yöneticisi & Ağ Kısıtlama")
        self.tab_downloader = self.tabview.add("🔗 Doğrudan URL İndirici")

        self._build_monitor_tab(self.tab_monitor)
        self._build_downloader_tab(self.tab_downloader)

    # ---------------------------------------------------------
    # TAB 1: Görev Yöneticisi & Canlı Ağ Kısıtlama
    # ---------------------------------------------------------
    def _build_monitor_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # A. Filter / Search Bar
        filter_bar = ctk.CTkFrame(parent, fg_color="transparent")
        filter_bar.grid(row=0, column=0, padx=8, pady=(4, 8), sticky="ew")
        filter_bar.grid_columnconfigure(0, weight=1)

        search_box = ctk.CTkFrame(filter_bar, fg_color="transparent")
        search_box.grid(row=0, column=0, sticky="w")

        self.search_entry = ctk.CTkEntry(
            search_box, placeholder_text="🔍 Uygulama Ara (örn: chrome, setup, steam)...",
            width=280, height=32
        )
        self.search_entry.pack(side="left", padx=(0, 10))

        self.check_only_active = ctk.CTkCheckBox(
            search_box, text="Sadece Ağ Trafiği Olanlar",
            font=ctk.CTkFont(size=12)
        )
        self.check_only_active.select()
        self.check_only_active.pack(side="left", padx=(0, 15))

        btn_box = ctk.CTkFrame(filter_bar, fg_color="transparent")
        btn_box.grid(row=0, column=1, sticky="e")

        self.btn_reset_all = ctk.CTkButton(
            btn_box, text="Tüm Limitleri Sıfırla",
            width=135, height=32,
            fg_color="#7f1d1d", hover_color="#991b1b",
            command=self._on_remove_all_limits
        )
        self.btn_reset_all.pack(side="right", padx=(6, 0))

        # B. Table Frame (Treeview)
        table_frame = ctk.CTkFrame(parent, corner_radius=8, fg_color=("#f3f4f6", "#181a1f"))
        table_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        # Style Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Task.Treeview",
            background="#1e2229",
            foreground="#f3f4f6",
            fieldbackground="#1e2229",
            rowheight=32,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.configure(
            "Task.Treeview.Heading",
            background="#282c35",
            foreground="#94a3b8",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padding=(6, 6)
        )
        style.map("Task.Treeview", background=[("selected", "#0284c7")])

        cols = ("pids", "down", "up", "conns", "total", "limit")
        self.tree = ttk.Treeview(
            table_frame,
            columns=cols,
            show="tree headings",
            selectmode="browse",
            style="Task.Treeview"
        )
        self.tree.heading("#0", text="  Uygulama Adı", anchor="w")
        self.tree.heading("pids", text="Süreç / PID", anchor="center")
        self.tree.heading("down", text="⬇ İndirme Hızı", anchor="e")
        self.tree.heading("up", text="⬆ Yükleme Hızı", anchor="e")
        self.tree.heading("conns", text="Bağlantı", anchor="center")
        self.tree.heading("total", text="Toplam Veri", anchor="e")
        self.tree.heading("limit", text="Mevcut Limit", anchor="center")

        self.tree.column("#0", width=220, minwidth=150)
        self.tree.column("pids", width=90, anchor="center")
        self.tree.column("down", width=120, anchor="e")
        self.tree.column("up", width=120, anchor="e")
        self.tree.column("conns", width=80, anchor="center")
        self.tree.column("total", width=110, anchor="e")
        self.tree.column("limit", width=130, anchor="center")

        scrollbar = ctk.CTkScrollbar(table_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # C. Interactive Throttling Control Card (Selected App)
        self.control_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=("gray85", "#1e2229"))
        self.control_card.grid(row=2, column=0, padx=8, pady=(0, 6), sticky="ew")
        self.control_card.grid_columnconfigure(1, weight=1)

        # Line 1: Target Process Badge
        lbl_target_title = ctk.CTkLabel(
            self.control_card, text="Seçili Uygulama:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl_target_title.grid(row=0, column=0, padx=(15, 10), pady=(10, 4), sticky="w")

        self.lbl_selected_app = ctk.CTkLabel(
            self.control_card, text="Tablodan bir uygulama seçin veya adını yazın",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_selected_app.grid(row=0, column=1, padx=0, pady=(10, 4), sticky="w")

        self.lbl_status_badge = ctk.CTkLabel(
            self.control_card, text="Limitsiz",
            fg_color="#334155", text_color="#cbd5e1",
            corner_radius=6, padx=8, pady=2,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_status_badge.grid(row=0, column=2, padx=(0, 15), pady=(10, 4), sticky="e")

        # Line 2: Speed Limit Input & Presets & Buttons
        action_frame = ctk.CTkFrame(self.control_card, fg_color="transparent")
        action_frame.grid(row=1, column=0, columnspan=3, padx=15, pady=(4, 12), sticky="ew")

        lbl_limit = ctk.CTkLabel(action_frame, text="Hız Sınırı:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_limit.pack(side="left", padx=(0, 8))

        self.entry_limit_val = ctk.CTkEntry(action_frame, width=80, height=32)
        self.entry_limit_val.insert(0, "500")
        self.entry_limit_val.pack(side="left", padx=(0, 6))

        self.combo_limit_unit = ctk.CTkComboBox(
            action_frame, values=["KB/s", "MB/s"], width=85, height=32
        )
        self.combo_limit_unit.set("KB/s")
        self.combo_limit_unit.pack(side="left", padx=(0, 12))

        # Quick preset buttons
        preset_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        preset_frame.pack(side="left", padx=(0, 15))

        for p_val, p_unit in [("250", "KB/s"), ("500", "KB/s"), ("1", "MB/s"), ("2", "MB/s"), ("5", "MB/s")]:
            btn_p = ctk.CTkButton(
                preset_frame, text=f"{p_val} {p_unit}", width=60, height=28,
                fg_color="#2b394a", hover_color="#36495f",
                font=ctk.CTkFont(size=11),
                command=lambda v=p_val, u=p_unit: self._set_preset(v, u)
            )
            btn_p.pack(side="left", padx=2)

        # Action Buttons
        self.btn_apply_limit = ctk.CTkButton(
            action_frame, text="⚡ Hızı Kısıtla",
            width=120, height=34,
            fg_color="#0284c7", hover_color="#0369a1",
            font=ctk.CTkFont(weight="bold"),
            command=self._on_apply_limit
        )
        self.btn_apply_limit.pack(side="right", padx=(6, 0))

        self.btn_remove_limit = ctk.CTkButton(
            action_frame, text="❌ Sınırı Kaldır",
            width=110, height=34,
            fg_color="#374151", hover_color="#4b5563",
            font=ctk.CTkFont(weight="bold"),
            command=self._on_remove_limit
        )
        self.btn_remove_limit.pack(side="right")

    # ---------------------------------------------------------
    # TAB 2: Doğrudan URL İndirici (Eski Mod)
    # ---------------------------------------------------------
    def _build_downloader_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(3, weight=1)

        # Input Card
        input_card = ctk.CTkFrame(parent, corner_radius=10)
        input_card.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        input_card.grid_columnconfigure(1, weight=1)

        url_lbl = ctk.CTkLabel(input_card, text="İndirme URL:", font=ctk.CTkFont(size=12, weight="bold"))
        url_lbl.grid(row=0, column=0, padx=12, pady=10, sticky="w")

        self.url_entry = ctk.CTkEntry(
            input_card, placeholder_text="https://speed.cloudflare.com/__down?bytes=25000000", height=34
        )
        self.url_entry.grid(row=0, column=1, padx=(0, 8), pady=10, sticky="ew")

        test_btn = ctk.CTkButton(
            input_card, text="Örnek URL", width=85, height=34,
            fg_color="#2b394a", hover_color="#36495f",
            command=lambda: (self.url_entry.delete(0, "end"), self.url_entry.insert(0, "https://speed.cloudflare.com/__down?bytes=25000000"))
        )
        test_btn.grid(row=0, column=2, padx=(0, 12), pady=10)

        # Download Settings
        set_card = ctk.CTkFrame(parent, corner_radius=10)
        set_card.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")

        lbl_dlimit = ctk.CTkLabel(set_card, text="İndirme Hız Limiti:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_dlimit.pack(side="left", padx=12, pady=10)

        self.entry_dlimit = ctk.CTkEntry(set_card, width=80, height=32)
        self.entry_dlimit.insert(0, "500")
        self.entry_dlimit.pack(side="left", padx=(0, 6))

        self.combo_dunit = ctk.CTkComboBox(set_card, values=["KB/s", "MB/s", "Sınırsız"], width=90, height=32)
        self.combo_dunit.set("KB/s")
        self.combo_dunit.pack(side="left", padx=(0, 15))

        self.btn_start_download = ctk.CTkButton(
            set_card, text="⬇ İndirmeyi Başlat", width=140, height=34,
            fg_color="#10b981", hover_color="#059669", font=ctk.CTkFont(weight="bold"),
            command=self._on_start_direct_download
        )
        self.btn_start_download.pack(side="right", padx=12, pady=10)

        # Telemetry
        self.lbl_telemetry = ctk.CTkLabel(
            parent, text="Durum: Hazır", font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.lbl_telemetry.grid(row=2, column=0, padx=12, pady=4, sticky="w")

        # Graph
        graph_card = ctk.CTkFrame(parent, corner_radius=10)
        graph_card.grid(row=3, column=0, padx=8, pady=(0, 8), sticky="nsew")
        graph_card.grid_columnconfigure(0, weight=1)
        graph_card.grid_rowconfigure(0, weight=1)

        self.speed_graph = SpeedGraphWidget(graph_card)
        self.speed_graph.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")

    # ---------------------------------------------------------
    # Event Handlers & Core Logic
    # ---------------------------------------------------------
    def _set_preset(self, val: str, unit: str):
        self.entry_limit_val.delete(0, "end")
        self.entry_limit_val.insert(0, val)
        self.combo_limit_unit.set(unit)

    def _on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        item_id = selected[0]
        app_name = self.tree.item(item_id, "text").strip()
        if not app_name:
            return

        self.selected_app = app_name
        self.lbl_selected_app.configure(text=app_name)

        # Check if already throttled
        limit_bytes = self.active_limits.get(app_name.lower())
        if limit_bytes:
            self.lbl_status_badge.configure(
                text=f"⚡ Kısıtlı: {format_speed(limit_bytes)}",
                fg_color="#854d0e", text_color="#fef08a"
            )
            # Fill inputs
            if limit_bytes >= 1024 * 1024:
                self.entry_limit_val.delete(0, "end")
                self.entry_limit_val.insert(0, str(int(limit_bytes / (1024 * 1024))))
                self.combo_limit_unit.set("MB/s")
            else:
                self.entry_limit_val.delete(0, "end")
                self.entry_limit_val.insert(0, str(int(limit_bytes / 1024)))
                self.combo_limit_unit.set("KB/s")
        else:
            self.lbl_status_badge.configure(
                text="Limitsiz",
                fg_color="#334155", text_color="#cbd5e1"
            )

    def _on_apply_limit(self):
        if not self.selected_app:
            # Let user type or pick from search entry if nothing selected
            q = self.search_entry.get().strip()
            if q:
                self.selected_app = q if q.endswith(".exe") else f"{q}.exe"
            else:
                messagebox.showwarning("Uygulama Seçilmedi", "Lütfen listeden hızını kısmak istediğiniz uygulamayı seçin.")
                return

        try:
            val = float(self.entry_limit_val.get().strip())
            unit = self.combo_limit_unit.get().strip()
            if val <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Geçersiz Hız", "Lütfen geçerli bir sayı girin (örn: 500).")
            return

        multiplier = 1024 * 1024 if unit == "MB/s" else 1024
        speed_bytes = int(val * multiplier)

        # Apply QoS Limit in background thread
        def _apply():
            ok, msg = QosManager.set_limit(self.selected_app, speed_bytes)
            self._refresh_active_limits()
            if ok:
                self.after(0, lambda: messagebox.showinfo(
                    "Limit Uygulandı",
                    f"'{self.selected_app}' için {val:.0f} {unit} indirme/ağ kısıtlaması başarıyla uygulandı."
                ))
            else:
                self.after(0, lambda: messagebox.showerror("İşlem Başarısız", f"Limit uygulanamadı:\n{msg}"))

        threading.Thread(target=_apply, daemon=True).start()

    def _on_remove_limit(self):
        if not self.selected_app:
            messagebox.showwarning("Uygulama Seçilmedi", "Lütfen kısıtlamasını kaldırmak istediğiniz uygulamayı seçin.")
            return

        def _remove():
            ok, msg = QosManager.remove_limit(self.selected_app)
            self._refresh_active_limits()
            if ok:
                self.after(0, lambda: messagebox.showinfo(
                    "Limit Kaldırıldı",
                    f"'{self.selected_app}' üzerindeki hız kısıtlaması kaldırıldı."
                ))
            else:
                self.after(0, lambda: messagebox.showerror("İşlem Başarısız", msg))

        threading.Thread(target=_remove, daemon=True).start()

    def _on_remove_all_limits(self):
        if not messagebox.askyesno("Tüm Limitleri Sıfırla", "Tüm uygulamalardaki aktif hız kısıtlamalarını kaldırmak istiyor musunuz?"):
            return

        def _clear():
            ok, msg = QosManager.remove_all_limits()
            self._refresh_active_limits()
            if ok:
                self.after(0, lambda: messagebox.showinfo("Tamamlandı", "Tüm aktif hız kısıtlamaları kaldırıldı."))
            else:
                self.after(0, lambda: messagebox.showerror("Hata", msg))

        threading.Thread(target=_clear, daemon=True).start()

    def _refresh_active_limits(self):
        def _fetch():
            limits = QosManager.get_active_limits()
            self.active_limits = limits

        threading.Thread(target=_fetch, daemon=True).start()

    # ---------------------------------------------------------
    # Direct Downloader Logic
    # ---------------------------------------------------------
    def _on_start_direct_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Eksik URL", "Lütfen geçerli bir indirme bağlantısı girin.")
            return

        unit = self.combo_dunit.get()
        if unit == "Sınırsız":
            limit_bytes = None
        else:
            try:
                v = float(self.entry_dlimit.get().strip())
                limit_bytes = int(v * (1024 * 1024 if unit == "MB/s" else 1024))
            except ValueError:
                limit_bytes = None

        self.download_engine.set_speed_limit(limit_bytes)
        self.download_engine.on_progress = self._on_download_progress
        self.download_engine.on_complete = lambda p: messagebox.showinfo("Tamamlandı", f"İndirildi: {p}")
        self.download_engine.start(url, self.download_dir)

    def _on_download_progress(self, metrics):
        speed = metrics.get("speed", 0.0)
        target = metrics.get("target_limit")
        downloaded = metrics.get("downloaded_bytes", 0)
        total = metrics.get("total_bytes", 0)
        self.lbl_telemetry.configure(
            text=f"İndiriliyor: {format_bytes(downloaded)} / {format_bytes(total)}  |  Hız: {format_speed(speed)}"
        )
        self.speed_graph.add_point(speed, target)

    # ---------------------------------------------------------
    # Periodic Live Updater (1 Hz)
    # ---------------------------------------------------------
    def _start_live_updater(self):
        self._update_task_table()

    def _update_task_table(self):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        query = self.search_entry.get().strip()
        only_active = bool(self.check_only_active.get())

        processes = self.monitor.get_processes(query=query, only_active_network=only_active)

        total_down = 0.0
        total_up = 0.0

        existing_items = set(self.tree.get_children())
        updated_items = set()

        for proc in processes:
            app_name = proc["name"]
            item_id = app_name.lower()
            updated_items.add(item_id)

            dr = proc["down_speed"]
            ur = proc["up_speed"]
            total_down += dr
            total_up += ur

            # Check if throttled
            limit_bytes = self.active_limits.get(app_name.lower())
            if limit_bytes:
                limit_str = f"⚡ {format_speed(limit_bytes)}"
            else:
                limit_str = "Limitsiz"

            vals = (
                proc["pid_display"],
                format_speed(dr) if dr > 0 else "0.0 KB/s",
                format_speed(ur) if ur > 0 else "0.0 KB/s",
                f"{proc['connections_count']} TCP" if proc["connections_count"] > 0 else "-",
                format_bytes(proc["total_down"]),
                limit_str
            )

            if item_id in existing_items:
                self.tree.item(item_id, values=vals)
            else:
                self.tree.insert("", "end", iid=item_id, text=f"  {app_name}", values=vals)

        # Remove dead items
        for old_id in existing_items - updated_items:
            try:
                self.tree.delete(old_id)
            except Exception:
                pass

        # Update top banner live total
        self.lbl_total_live.configure(
            text=f"⬇ {format_speed(total_down)}  |  ⬆ {format_speed(total_up)}"
        )

        # Schedule next update in 900ms
        self.after(900, self._update_task_table)

    def _toggle_theme(self, mode: str):
        ctk.set_appearance_mode("Dark" if mode == "Karanlık" else "Light")


def launch():
    app = BandwidthLimiterApp()
    app.mainloop()

if __name__ == "__main__":
    launch()
