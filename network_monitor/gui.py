"""Real-time tkinter dashboard for network monitoring."""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from network_monitor.config import DOWN_FLASH_INTERVAL, GUI_REFRESH_MS
from network_monitor.models import Status
from network_monitor.monitor import NetworkMonitor


# Colour palette
COLOR_UP_BG = "#1a7f37"
COLOR_UP_FG = "#ffffff"
COLOR_DOWN_BG = "#c41e3a"
COLOR_DOWN_FG = "#ffffff"
COLOR_DOWN_FLASH = "#ff1744"
COLOR_HEADER_BG = "#1e1e2e"
COLOR_HEADER_FG = "#cdd6f4"
COLOR_ROW_ALT = "#2a2a3d"
COLOR_ROW_BG = "#242433"
COLOR_SUMMARY_OK = "#1a7f37"
COLOR_SUMMARY_ALERT = "#c41e3a"


class MonitorGUI:
    """NOC-style dashboard with high-visibility DOWN alerts."""

    COLUMNS = ("name", "ip", "status", "latency", "last_seen", "last_check")

    def __init__(self, monitor: NetworkMonitor) -> None:
        self.monitor = monitor
        self._flash_tick = 0
        self._flash_on = False

        self.root = tk.Tk()
        self.root.title("Network Monitor — Supervision ICMP")
        self.root.geometry("960x600")
        self.root.minsize(720, 400)
        self.root.configure(bg=COLOR_HEADER_BG)

        self._setup_styles()
        self._build_header()
        self._build_table()
        self._build_footer()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=COLOR_ROW_BG,
            foreground=COLOR_HEADER_FG,
            fieldbackground=COLOR_ROW_BG,
            rowheight=36,
            font=("Segoe UI", 11),
        )
        style.configure(
            "Treeview.Heading",
            background=COLOR_HEADER_BG,
            foreground=COLOR_HEADER_FG,
            font=("Segoe UI", 11, "bold"),
        )
        style.map("Treeview", background=[("selected", "#45475a")])

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=COLOR_HEADER_BG, pady=12, padx=16)
        header.pack(fill=tk.X)

        title_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        tk.Label(
            header,
            text="NETWORK MONITOR",
            font=title_font,
            bg=COLOR_HEADER_BG,
            fg=COLOR_HEADER_FG,
        ).pack(side=tk.LEFT)

        self.summary_label = tk.Label(
            header,
            text="",
            font=("Segoe UI", 13, "bold"),
            bg=COLOR_HEADER_BG,
            fg=COLOR_HEADER_FG,
            padx=20,
        )
        self.summary_label.pack(side=tk.RIGHT)

        self.alert_banner = tk.Label(
            self.root,
            text="",
            font=("Segoe UI", 14, "bold"),
            bg=COLOR_SUMMARY_ALERT,
            fg="#ffffff",
            pady=8,
        )
        # packed dynamically when DOWN machines exist

    def _build_table(self) -> None:
        frame = tk.Frame(self.root, bg=COLOR_HEADER_BG, padx=16, pady=8)
        frame.pack(fill=tk.BOTH, expand=True)

        headings = {
            "name": ("Machine", 160),
            "ip": ("IP", 140),
            "status": ("Statut", 90),
            "latency": ("Latence (ms)", 110),
            "last_seen": ("Last seen", 160),
            "last_check": ("Dernier check", 160),
        }

        self.tree = ttk.Treeview(
            frame,
            columns=self.COLUMNS,
            show="headings",
            selectmode="browse",
        )

        for col, (label, width) in headings.items():
            self.tree.heading(col, text=label)
            anchor = tk.CENTER if col in ("status", "latency") else tk.W
            self.tree.column(col, width=width, anchor=anchor, stretch=(col == "name"))

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Row colour tags
        self.tree.tag_configure("up", background=COLOR_UP_BG, foreground=COLOR_UP_FG)
        self.tree.tag_configure(
            "down", background=COLOR_DOWN_BG, foreground=COLOR_DOWN_FG
        )
        self.tree.tag_configure(
            "down_flash",
            background=COLOR_DOWN_FLASH,
            foreground=COLOR_DOWN_FG,
        )
        self.tree.tag_configure("idle_up", background=COLOR_ROW_BG, foreground=COLOR_UP_BG)

    def _build_footer(self) -> None:
        footer = tk.Frame(self.root, bg=COLOR_HEADER_BG, pady=8, padx=16)
        footer.pack(fill=tk.X)

        self.status_bar = tk.Label(
            footer,
            text="Démarrage…",
            font=("Segoe UI", 9),
            bg=COLOR_HEADER_BG,
            fg="#888899",
            anchor=tk.W,
        )
        self.status_bar.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # Refresh loop
    # ------------------------------------------------------------------

    def _schedule_refresh(self) -> None:
        self._refresh()
        self.root.after(GUI_REFRESH_MS, self._schedule_refresh)

    def _refresh(self) -> None:
        snapshot = self.monitor.get_snapshot()
        self._flash_tick += 1
        if self._flash_tick % DOWN_FLASH_INTERVAL == 0:
            self._flash_on = not self._flash_on

        # Summary + alert banner
        if snapshot.down_count > 0:
            summary_text = (
                f"  {snapshot.up_count} UP  |  "
                f"{snapshot.down_count} DOWN  "
            )
            self.summary_label.configure(
                text=summary_text, fg=COLOR_SUMMARY_ALERT
            )
            down_names = ", ".join(
                m.name for m in snapshot.machines if m.status == Status.DOWN
            )
            self.alert_banner.configure(
                text=f"  ALERTE — MACHINE(S) DOWN : {down_names}  "
            )
            self.alert_banner.pack(fill=tk.X, before=self.tree.master)
            self.root.configure(bg=COLOR_SUMMARY_ALERT)
        else:
            self.summary_label.configure(
                text=f"  {snapshot.up_count} UP  |  0 DOWN  ",
                fg=COLOR_SUMMARY_OK,
            )
            self.alert_banner.pack_forget()
            self.root.configure(bg=COLOR_HEADER_BG)

        # Rebuild tree rows (simple & reliable for small inventories)
        for item in self.tree.get_children():
            self.tree.delete(item)

        for machine in snapshot.machines:
            is_up = machine.status == Status.UP
            latency = (
                f"{machine.latency_ms:.1f}" if machine.latency_ms is not None else "—"
            )
            last_seen = (
                machine.last_seen.strftime("%H:%M:%S") if machine.last_seen else "—"
            )
            last_check = (
                machine.last_check.strftime("%H:%M:%S") if machine.last_check else "—"
            )

            if is_up:
                tag = "up"
            elif self._flash_on:
                tag = "down_flash"
            else:
                tag = "down"

            self.tree.insert(
                "",
                tk.END,
                values=(
                    machine.name,
                    machine.ip,
                    machine.status.value,
                    latency,
                    last_seen,
                    last_check,
                ),
                tags=(tag,),
            )

        cycle = (
            snapshot.last_cycle.strftime("%Y-%m-%d %H:%M:%S")
            if snapshot.last_cycle
            else "—"
        )
        self.status_bar.configure(
            text=f"Dernier cycle : {cycle}  |  "
            f"UP → ping 60 s  |  DOWN → ping 3 s  |  "
            f"Rafraîchissement GUI : {GUI_REFRESH_MS} ms"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self.monitor.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
