# ==============================================================================
# SECTION: DESCRIPTION
# ==============================================================================
"""
Real-time tkinter dashboard for network monitoring.

Displays a NOC-style panel with two tabs:
  - Current DOWN — machines that failed their most recent ping.
  - Archive     — completed downtime incidents with timestamps and durations.
"""

# ==============================================================================
# SECTION: IMPORTS
# ==============================================================================

# Import tkinter for the main GUI window and widget construction.
import tkinter as tk
# Import tkinter font module for custom font definitions.
from tkinter import font as tkfont
# Import themed widgets (Treeview, Notebook, Scrollbar).
from tkinter import ttk
# Import message box dialogs (info, error, yes/no prompts).
from tkinter import messagebox
# Import file browser dialog for choosing export directories.
from tkinter import filedialog

# Import GUI timing constants from the unified configuration module.
from network_monitor.config import (
    DOWN_FLASH_INTERVAL,
    GUI_REFRESH_MS,
    load_sections,
    save_sections,
    get_section_color,
    get_sections_dict,
)
# Import data models for machine status checks.
from network_monitor.models import Status, Machine
# Import the background monitoring engine class.
from network_monitor.monitor import NetworkMonitor

# ==============================================================================
# SECTION: COLOUR PALETTE
# ==============================================================================

# Background colour for rows showing DOWN machines.
COLOR_DOWN_BG = "#c41e3a"
# Foreground (text) colour for DOWN machine rows.
COLOR_DOWN_FG = "#ffffff"
# Alternating flash colour for DOWN machine rows (draws attention).
COLOR_DOWN_FLASH = "#ff1744"
# Dark background colour for headers and panels.
COLOR_HEADER_BG = "#1e1e2e"
# Light text colour for header labels.
COLOR_HEADER_FG = "#cdd6f4"
# Background colour for normal table rows.
COLOR_ROW_BG = "#242433"
# Colour for the alert banner shown when machines are DOWN.
COLOR_SUMMARY_ALERT = "#c41e3a"


# ==============================================================================
# SECTION: MAIN GUI CLASS
# ==============================================================================

class MonitorGUI:
    """NOC-style dashboard with high-visibility DOWN alerts."""

    # Column identifiers used in the "Current DOWN" Treeview table.
    COLUMNS = ("name", "ip", "status", "down_since", "last_check")

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def __init__(self, monitor: NetworkMonitor) -> None:
        # Store a reference to the background monitoring engine.
        self.monitor = monitor
        # Counter used to alternate the flash colour on DOWN rows.
        self._flash_tick = 0
        # Boolean toggled every N ticks to switch between red shades.
        self._flash_on = False

        # Create the main application window.
        self.root = tk.Tk()
        # Set the window title.
        self.root.title("Network Monitor — Supervision ICMP")
        # Set the initial window dimensions.
        self.root.geometry("1100x650")
        # Set the minimum allowed window size.
        self.root.minsize(800, 450)
        # Apply the dark background colour.
        self.root.configure(bg=COLOR_HEADER_BG)

        # Configure visual styles for all Treeview/Notebook widgets.
        self._setup_styles()
        # Build the top header bar with title and action buttons.
        self._build_header()
        # Build the tabbed notebook with Current DOWN and Archive tabs.
        self._build_notebook()
        # Build the bottom status bar.
        self._build_footer()

        # Register a handler to run when the user closes the window.
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Start the periodic GUI refresh loop.
        self._schedule_refresh()

    # ------------------------------------------------------------------
    # Style configuration
    # ------------------------------------------------------------------

    def _setup_styles(self) -> None:
        """Configure ttk styles for Treeview and Notebook widgets."""
        # Create a style object bound to the root window.
        style = ttk.Style(self.root)
        # Use the 'clam' theme as a base for custom styling.
        style.theme_use("clam")

        # Style for table body rows.
        style.configure(
            "Treeview",
            background=COLOR_ROW_BG,
            foreground=COLOR_HEADER_FG,
            fieldbackground=COLOR_ROW_BG,
            rowheight=36,
            font=("Segoe UI", 11),
        )
        # Style for table column headers.
        style.configure(
            "Treeview.Heading",
            background=COLOR_HEADER_BG,
            foreground=COLOR_HEADER_FG,
            font=("Segoe UI", 11, "bold"),
        )
        # Hover highlight colour for column headers.
        style.map(
            "Treeview.Heading",
            background=[("active", "#313244")],
            foreground=[("active", "#ffffff")],
        )
        # Selected row highlight colour.
        style.map("Treeview", background=[("selected", "#45475a")])

        # Style for the Notebook (tab container).
        style.configure("TNotebook", background=COLOR_HEADER_BG, borderwidth=0)
        # Style for individual tabs.
        style.configure(
            "TNotebook.Tab",
            background="#3a4a5a",
            foreground=COLOR_HEADER_FG,
            padding=[15, 6],
            font=("Segoe UI", 10, "bold"),
        )
        # Active tab styling.
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLOR_ROW_BG)],
            foreground=[("selected", "#ffffff")],
        )

    # ------------------------------------------------------------------
    # Header construction
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        """Build the top header bar with title and action buttons."""
        # Create a frame for the header row.
        header = tk.Frame(self.root, bg=COLOR_HEADER_BG, pady=12, padx=16)
        header.pack(fill=tk.X)

        # Create a bold title font.
        title_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        # Add the application title label.
        tk.Label(
            header,
            text="NETWORK MONITOR",
            font=title_font,
            bg=COLOR_HEADER_BG,
            fg=COLOR_HEADER_FG,
        ).pack(side=tk.LEFT)

        # Add the "Edit Machines" button to open the inventory editor.
        tk.Button(
            header,
            text="✎ Edit Machines",
            command=self._open_machines_editor,
            bg="#3a4a5a",
            fg=COLOR_HEADER_FG,
            font=("Segoe UI", 10),
            padx=10,
            pady=5,
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=10)

        # Add the "Settings" button to open application preferences.
        tk.Button(
            header,
            text="⚙ Settings",
            command=self._open_settings,
            bg="#3a4a5a",
            fg=COLOR_HEADER_FG,
            font=("Segoe UI", 10),
            padx=10,
            pady=5,
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=10)

        # Create the alert banner label (shown only when machines are DOWN).
        self.alert_banner = tk.Label(
            self.root,
            text="",
            font=("Segoe UI", 14, "bold"),
            bg=COLOR_SUMMARY_ALERT,
            fg="#ffffff",
            pady=8,
        )
        # The banner is packed dynamically during refresh when DOWN machines exist.

    # ------------------------------------------------------------------
    # Notebook (tabs) construction
    # ------------------------------------------------------------------

    def _build_notebook(self) -> None:
        """Build the tabbed interface with Current DOWN and Archive tabs."""
        # Create a container frame for the notebook.
        container = tk.Frame(self.root, bg=COLOR_HEADER_BG, padx=16, pady=8)
        container.pack(fill=tk.BOTH, expand=True)

        # Create the notebook widget for tab switching.
        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create the "Current DOWN" tab frame.
        self.current_frame = tk.Frame(self.notebook, bg=COLOR_HEADER_BG)
        self.notebook.add(self.current_frame, text="Current DOWN")
        self._build_current_tab()

        # Create the "Archive" tab frame.
        self.archive_frame = tk.Frame(self.notebook, bg=COLOR_HEADER_BG)
        self.notebook.add(self.archive_frame, text="Archive")
        self._build_archive_tab()

    def _build_current_tab(self) -> None:
        """Build the Treeview table showing currently DOWN machines."""
        # Define column labels and widths.
        headings = {
            "name": ("Machine", 160),
            "ip": ("IP", 140),
            "status": ("Status", 90),
            "down_since": ("Went Down", 160),
            "last_check": ("Last check", 160),
        }

        # Create the Treeview table widget.
        self.tree = ttk.Treeview(
            self.current_frame,
            columns=self.COLUMNS,
            show="headings",
            selectmode="browse",
        )

        # Configure each column heading and alignment.
        for col, (label, width) in headings.items():
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=tk.CENTER, stretch=(col == "name"))

        # Add a vertical scrollbar linked to the Treeview.
        vsb = ttk.Scrollbar(self.current_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        # Pack the tree and scrollbar into the tab frame.
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the steady red tag for DOWN rows.
        self.tree.tag_configure("down", background=COLOR_DOWN_BG, foreground=COLOR_DOWN_FG)
        # Configure the flashing brighter red tag for DOWN rows.
        self.tree.tag_configure("down_flash", background=COLOR_DOWN_FLASH, foreground=COLOR_DOWN_FG)

    def _build_archive_tab(self) -> None:
        """Build the Treeview table showing historical downtime incidents."""
        # Create a toolbar frame with Export and Clear buttons.
        toolbar = tk.Frame(self.archive_frame, bg=COLOR_HEADER_BG, pady=6, padx=16)
        toolbar.pack(fill=tk.X)

        # Export button — saves the archive to a CSV file.
        tk.Button(
            toolbar,
            text="💾 Export",
            command=self._export_archive,
            bg="#2a7f37",
            fg="#ffffff",
            font=("Segoe UI", 10),
            padx=10,
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=3)

        # Clear button — removes all archive records.
        tk.Button(
            toolbar,
            text="✕ Clear",
            command=self._clear_archive,
            bg="#c41e3a",
            fg="#ffffff",
            font=("Segoe UI", 10),
            padx=10,
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=3)

        # Define archive table column identifiers.
        archive_columns = ("machine", "ip", "went_down", "came_back_up", "duration")

        # Create a container frame for the archive Treeview.
        tree_container = tk.Frame(self.archive_frame, bg=COLOR_HEADER_BG)
        tree_container.pack(fill=tk.BOTH, expand=True)

        # Create the archive Treeview table widget.
        self.archive_tree = ttk.Treeview(
            tree_container,
            columns=archive_columns,
            show="headings",
            selectmode="browse",
        )

        # Define column labels and widths for the archive table.
        headings = {
            "machine": ("Machine", 150),
            "ip": ("IP", 140),
            "went_down": ("Went DOWN", 180),
            "came_back_up": ("Came Back UP", 180),
            "duration": ("Duration", 140),
        }

        # Configure each column heading and alignment.
        for col, (label, width) in headings.items():
            self.archive_tree.heading(col, text=label)
            self.archive_tree.column(col, width=width, anchor=tk.CENTER)

        # Add a vertical scrollbar linked to the archive Treeview.
        vsb = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.archive_tree.yview)
        self.archive_tree.configure(yscrollcommand=vsb.set)

        # Pack the tree and scrollbar into the tab frame.
        self.archive_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the default row styling for archive entries.
        self.archive_tree.tag_configure("archive_row", background=COLOR_ROW_BG, foreground=COLOR_HEADER_FG)

    # ------------------------------------------------------------------
    # Archive actions
    # ------------------------------------------------------------------

    def _export_archive(self) -> None:
        """Export the downtime archive to a CSV file."""
        try:
            # Call the monitor engine's export function.
            filepath = self.monitor.export_archive()
            if filepath:
                # Show success dialog with file path.
                messagebox.showinfo("Export Successful", f"Archive exported to:\n{filepath}")
            else:
                # Inform user there are no records to export.
                messagebox.showinfo("Export", "No records to export.")
        except Exception as e:
            # Show error dialog if export fails.
            messagebox.showerror("Export Failed", f"Failed to export archive:\n{e}")

    def _clear_archive(self) -> None:
        """Clear all archive records after user confirmation."""
        # Ask the user to confirm the clear action.
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all archive records?"):
            # Clear the archive and get the count of removed records.
            count = self.monitor.clear_archive()
            # Show confirmation dialog.
            messagebox.showinfo("Archive Cleared", f"Cleared {count} records from the archive.")
            # Force an immediate GUI refresh.
            self._refresh()

    # ------------------------------------------------------------------
    # Footer construction
    # ------------------------------------------------------------------

    def _build_footer(self) -> None:
        """Build the bottom status bar displaying cycle information."""
        # Create a frame for the footer row.
        footer = tk.Frame(self.root, bg=COLOR_HEADER_BG, pady=8, padx=16)
        footer.pack(fill=tk.X)

        # Create the status bar label.
        self.status_bar = tk.Label(
            footer,
            text="Starting...",
            font=("Segoe UI", 9),
            bg=COLOR_HEADER_BG,
            fg="#888899",
            anchor=tk.W,
        )
        self.status_bar.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # Periodic refresh loop
    # ------------------------------------------------------------------

    def _schedule_refresh(self) -> None:
        """Schedule the next GUI refresh cycle."""
        # Run the refresh immediately.
        self._refresh()
        # Schedule the next refresh after GUI_REFRESH_MS milliseconds.
        self.root.after(GUI_REFRESH_MS, self._schedule_refresh)

    def _refresh(self) -> None:
        """Refresh all GUI tables and status displays from monitor data."""
        # Get a thread-safe snapshot from the monitor engine.
        snapshot = self.monitor.get_snapshot()

        # Increment the flash tick counter.
        self._flash_tick += 1
        # Toggle flash state every N ticks.
        if self._flash_tick % DOWN_FLASH_INTERVAL == 0:
            self._flash_on = not self._flash_on

        # --- Alert banner ---
        if snapshot.down_count > 0:
            # Update the banner text with the number of DOWN machines.
            self.alert_banner.configure(
                text=f"  ALERT — {snapshot.down_count} MACHINE(S) DOWN  "
            )
            # Show the banner above the notebook.
            self.alert_banner.pack(fill=tk.X, before=self.notebook.master)
            # Change the root background to alert colour.
            self.root.configure(bg=COLOR_SUMMARY_ALERT)
        else:
            # Hide the banner when all machines are UP.
            self.alert_banner.pack_forget()
            # Restore the normal background colour.
            self.root.configure(bg=COLOR_HEADER_BG)

        # --- Rebuild Current DOWN table ---
        # Clear all existing rows.
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Insert a row for each DOWN machine.
        for machine in snapshot.machines:
            # Skip machines that are UP (this tab only shows DOWN).
            if machine.status == Status.UP:
                continue

            # Format the "down since" timestamp.
            down_since = (
                machine.down_since.strftime("%Y-%m-%d %H:%M:%S") if machine.down_since else "—"
            )
            # Format the "last check" timestamp.
            last_check = (
                machine.last_check.strftime("%H:%M:%S") if machine.last_check else "—"
            )

            # Alternate between red shades for visual emphasis.
            tag = "down_flash" if self._flash_on else "down"

            # Insert the row into the Treeview.
            self.tree.insert(
                "",
                tk.END,
                values=(machine.name, machine.ip, machine.status.value, down_since, last_check),
                tags=(tag,),
            )

        # --- Rebuild Archive table ---
        # Clear all existing archive rows.
        for item in self.archive_tree.get_children():
            self.archive_tree.delete(item)

        # Insert a row for each historical downtime incident.
        for record in snapshot.archive:
            # Format timestamps.
            went_down_str = record.went_down.strftime("%Y-%m-%d %H:%M:%S")
            came_back_up_str = record.came_back_up.strftime("%Y-%m-%d %H:%M:%S")

            # Calculate and format the duration.
            total_seconds = int(record.duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            # Insert the archive row.
            self.archive_tree.insert(
                "",
                tk.END,
                values=(record.machine_name, record.machine_ip, went_down_str, came_back_up_str, duration_str),
                tags=("archive_row",),
            )

        # --- Update footer status bar ---
        # Format the last cycle timestamp.
        cycle = snapshot.last_cycle.strftime("%Y-%m-%d %H:%M:%S") if snapshot.last_cycle else "—"
        # Update the status bar text.
        self.status_bar.configure(
            text=(
                f"Last cycle: {cycle}  |  "
                f"View: DOWN only + Archive  |  "
                f"GUI Refresh: {GUI_REFRESH_MS} ms  |  "
                f"Archive entries: {len(snapshot.archive)}"
            )
        )

    # ------------------------------------------------------------------
    # Modal dialogs (Machines Editor & Settings)
    # ------------------------------------------------------------------

    def _open_machines_editor(self) -> None:
        """Open the machines editor modal window."""
        # Import the editor window class (lazy import to avoid circular dependencies).
        from network_monitor.gui_editors import MachinesEditorWindow
        # Create the editor window as a child of the main window.
        editor = MachinesEditorWindow(self.root, self.monitor)
        # Block until the editor window is closed.
        self.root.wait_window(editor.window)

    def _open_settings(self) -> None:
        """Open the application settings modal dialog."""
        # Create the settings dialog as a child of the main window.
        settings = SettingsDialog(self.root, self.monitor)
        # Block until the settings dialog is closed.
        self.root.wait_window(settings.window)

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        """Handle window close: stop the monitor and destroy the window."""
        # Signal the background threads to stop.
        self.monitor.stop()
        # Destroy the main tkinter window.
        self.root.destroy()

    def run(self) -> None:
        """Start the tkinter main event loop (blocks until window closes)."""
        self.root.mainloop()


# ==============================================================================
# SECTION: SETTINGS DIALOG CLASS
# ==============================================================================

class SettingsDialog:
    """Modal dialog for editing application settings."""

    def __init__(self, parent: tk.Tk, monitor: NetworkMonitor) -> None:
        # Store a reference to the monitor engine.
        self.monitor = monitor
        # Load the current settings into a working copy.
        self.settings = monitor.get_settings().copy()

        # Create a top-level child window.
        self.window = tk.Toplevel(parent)
        self.window.title("Settings")
        self.window.geometry("600x400")
        self.window.minsize(400, 300)
        self.window.configure(bg=COLOR_HEADER_BG)

        # Make the dialog stay on top of and bound to the parent window.
        self.window.transient(parent)
        # Grab input focus — user must close this before interacting with the main window.
        self.window.grab_set()

        # Bind click events to play a warning bell if user clicks outside this dialog.
        def _on_click_outside(event):
            if event.widget == self.window:
                x, y = event.x_root, event.y_root
                x0 = self.window.winfo_rootx()
                y0 = self.window.winfo_rooty()
                x1 = x0 + self.window.winfo_width()
                y1 = y0 + self.window.winfo_height()
                if not (x0 <= x <= x1 and y0 <= y <= y1):
                    self.window.bell()

        self.window.bind("<ButtonPress>", _on_click_outside)

        # Build the settings form.
        self._build_ui()

    def _build_ui(self) -> None:
        """Create form widgets for editing each setting."""
        # Create the main padded frame.
        main_frame = tk.Frame(self.window, bg=COLOR_HEADER_BG, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Polling Interval ---
        tk.Label(
            main_frame, text="Polling Interval (seconds):",
            bg=COLOR_HEADER_BG, fg=COLOR_HEADER_FG, font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky=tk.W, pady=10)

        self.polling_interval_var = tk.IntVar(value=self.settings.get("polling_interval_sec", 60))
        tk.Spinbox(
            main_frame, from_=5, to=3600,
            textvariable=self.polling_interval_var, width=15, font=("Segoe UI", 10),
        ).grid(row=0, column=1, sticky=tk.W, pady=10)

        tk.Label(
            main_frame, text="(min: 5, max: 3600)",
            bg=COLOR_HEADER_BG, fg="#888899", font=("Segoe UI", 9),
        ).grid(row=0, column=2, sticky=tk.W, padx=10)

        # --- Archive Export Days ---
        tk.Label(
            main_frame, text="Archive Export Interval (days):",
            bg=COLOR_HEADER_BG, fg=COLOR_HEADER_FG, font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky=tk.W, pady=10)

        self.export_days_var = tk.IntVar(value=self.settings.get("archive_export_days", 30))
        tk.Spinbox(
            main_frame, from_=1, to=365,
            textvariable=self.export_days_var, width=15, font=("Segoe UI", 10),
        ).grid(row=1, column=1, sticky=tk.W, pady=10)

        tk.Label(
            main_frame, text="(min: 1, max: 365)",
            bg=COLOR_HEADER_BG, fg="#888899", font=("Segoe UI", 9),
        ).grid(row=1, column=2, sticky=tk.W, padx=10)

        # --- Archive Export Prefix ---
        tk.Label(
            main_frame, text="CSV Filename Prefix:",
            bg=COLOR_HEADER_BG, fg=COLOR_HEADER_FG, font=("Segoe UI", 10),
        ).grid(row=2, column=0, sticky=tk.W, pady=10)

        self.prefix_var = tk.StringVar(value=self.settings.get("archive_export_prefix", "downtime_archive"))
        tk.Entry(
            main_frame, textvariable=self.prefix_var, width=30, font=("Segoe UI", 10),
        ).grid(row=2, column=1, columnspan=2, sticky=tk.EW, pady=10)

        # --- Logs Directory ---
        tk.Label(
            main_frame, text="Logs Directory:",
            bg=COLOR_HEADER_BG, fg=COLOR_HEADER_FG, font=("Segoe UI", 10),
        ).grid(row=3, column=0, sticky=tk.W, pady=10)

        logs_dir_frame = tk.Frame(main_frame, bg=COLOR_HEADER_BG)
        logs_dir_frame.grid(row=3, column=1, columnspan=2, sticky=tk.EW, pady=10)

        self.logs_dir_var = tk.StringVar(value=self.settings.get("logs_directory", "logs"))
        tk.Entry(
            logs_dir_frame, textvariable=self.logs_dir_var, width=25, font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            logs_dir_frame, text="Browse", command=self._browse_directory,
            bg="#3a4a5a", fg=COLOR_HEADER_FG, font=("Segoe UI", 10), relief=tk.FLAT, padx=10,
        ).pack(side=tk.LEFT, padx=5)

        # --- Action Buttons ---
        button_frame = tk.Frame(main_frame, bg=COLOR_HEADER_BG)
        button_frame.grid(row=4, column=0, columnspan=3, pady=20)

        # Cancel button — closes without saving.
        tk.Button(
            button_frame, text="Cancel", command=self.window.destroy,
            bg="#3a4a5a", fg=COLOR_HEADER_FG, font=("Segoe UI", 10), width=12, relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=5)

        # Save button — validates and persists settings.
        tk.Button(
            button_frame, text="Save", command=self._save_settings,
            bg="#2a7f37", fg="#ffffff", font=("Segoe UI", 10), width=12, relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=5)

        # Allow the middle column to stretch.
        main_frame.columnconfigure(1, weight=1)

    def _browse_directory(self) -> None:
        """Open a file browser to select the logs output directory."""
        directory = filedialog.askdirectory(
            title="Select Logs Directory",
            initialdir=self.logs_dir_var.get(),
        )
        if directory:
            self.logs_dir_var.set(directory)

    def _save_settings(self) -> None:
        """Validate inputs, save settings to disk, and close the dialog."""
        try:
            # Read and validate polling interval.
            polling_interval = self.polling_interval_var.get()
            if polling_interval < 5:
                raise ValueError("Polling interval must be at least 5 seconds")
            if polling_interval > 3600:
                raise ValueError("Polling interval must be at most 3600 seconds")

            # Read and validate export days.
            export_days = self.export_days_var.get()
            if export_days < 1 or export_days > 365:
                raise ValueError("Export interval must be between 1 and 365 days")

            # Read and validate CSV prefix.
            prefix = self.prefix_var.get().strip()
            if not prefix:
                raise ValueError("CSV prefix cannot be empty")

            # Read and validate logs directory.
            logs_dir = self.logs_dir_var.get().strip()
            if not logs_dir:
                raise ValueError("Logs directory cannot be empty")

            # Build the updated settings dictionary.
            self.settings = {
                "polling_interval_sec": polling_interval,
                "archive_export_days": export_days,
                "archive_export_prefix": prefix,
                "logs_directory": logs_dir,
            }

            # Push settings to the monitor engine (saves to disk).
            self.monitor.update_settings(self.settings)
            # Show success confirmation.
            messagebox.showinfo("Success", "Settings saved!")
            # Close the dialog.
            self.window.destroy()

        except ValueError as e:
            # Show validation error message.
            messagebox.showerror("Validation Error", str(e))
