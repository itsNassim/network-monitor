# Import Tkinter for GUI components and windows
import tkinter as tk
# Import ttk, messagebox, and colorchooser dialogs from Tkinter package
from tkinter import ttk, messagebox, colorchooser

# Import Machine data structure
from network_monitor.models import Machine
# Import the NetworkMonitor engine controller class
from network_monitor.monitor import NetworkMonitor
# Import functions to read and write section preferences
from network_monitor.config import load_sections, save_sections

# Color theme configuration settings (must match colors in gui.py)
COLOR_HEADER_BG = "#1e1e2e"     # Deep dark blue-gray background color for titlebars and panels
COLOR_HEADER_FG = "#cdd6f4"     # Light lavender-white text color for labels
COLOR_ROW_BG = "#242433"        # Slightly lighter charcoal background for list/table rows


class SectionEditorDialog:
    """Dialog for creating/editing a section (name + color)."""

    # Grid of predefined color presets to offer user when creating/editing a section
    PRESET_COLORS = [
        ("#2d5a3d", "Green"), ("#3d4a6a", "Blue"), ("#5a3d4a", "Purple"),
        ("#2d5a5a", "Teal"), ("#4a3d2d", "Brown"), ("#5a4a2d", "Orange"),
        ("#3d5a4a", "Cyan"), ("#4a2d5a", "Magenta"), ("#5a3d2d", "Red-Brown"),
        ("#2d4a5a", "Dark Blue"), ("#6a3d3d", "Crimson"), ("#3d6a3d", "Forest"),
    ]

    def __init__(self, parent, name: str = "", color: str = "#4a5a7a") -> None:
        # Holds the final chosen section name and hex color
        self.result = None
        # Track active color selection
        self.selected_color = color

        # Create a new top-level subwindow
        self.window = tk.Toplevel(parent)
        # Apply relevant window title depending on whether editing or creating
        self.window.title("Create Section" if not name else "Edit Section")
        # Define window dimensions
        self.window.geometry("420x370")
        # Set custom dark background color
        self.window.configure(bg=COLOR_HEADER_BG)
        # Block resizing window to keep layout clean and predictable
        self.window.resizable(False, False)

        # --- Section Name Input ---
        tk.Label(self.window, text="Section Name:", bg=COLOR_HEADER_BG,
                 fg=COLOR_HEADER_FG, font=("Segoe UI", 10)
                 ).grid(row=0, column=0, sticky=tk.W, padx=16, pady=(16, 8))

        self.name_entry = tk.Entry(self.window, font=("Segoe UI", 11), width=28)
        self.name_entry.grid(row=0, column=1, sticky=tk.EW, padx=16, pady=(16, 8))
        if name:
            # Pre-populate field with current section name
            self.name_entry.insert(0, name)

        # --- Section Color Preview ---
        tk.Label(self.window, text="Section Color:", bg=COLOR_HEADER_BG,
                 fg=COLOR_HEADER_FG, font=("Segoe UI", 10)
                 ).grid(row=1, column=0, sticky=tk.NW, padx=16, pady=8)

        self.preview = tk.Label(self.window, text="  ■ Preview  ", bg=color,
                                fg="#ffffff", font=("Segoe UI", 12, "bold"),
                                padx=10, pady=4)
        self.preview.grid(row=1, column=1, sticky=tk.W, padx=16, pady=8)

        # --- Preset Palette Container ---
        palette_frame = tk.Frame(self.window, bg=COLOR_HEADER_BG)
        palette_frame.grid(row=2, column=0, columnspan=2, padx=16, pady=8, sticky=tk.EW)

        self.color_btns = []
        # Populate grid with color preset buttons
        for i, (hex_c, label) in enumerate(self.PRESET_COLORS):
            # Highlight selected color with border border thickness
            btn = tk.Button(palette_frame, text="■", bg=hex_c, fg="#ffffff",
                            font=("Segoe UI", 10), width=3, height=1,
                            bd=3 if hex_c == color else 1,
                            relief=tk.SUNKEN if hex_c == color else tk.RAISED,
                            command=lambda c=hex_c: self._pick_preset(c))
            # Grid layout arranges buttons in 6 columns
            btn.grid(row=i // 6, column=i % 6, padx=2, pady=2)
            # Retain references to button objects to dynamically toggle borders later
            self.color_btns.append((btn, hex_c))

        # Button to open system custom color picker
        tk.Button(palette_frame, text="Custom…", bg="#3a4a5a", fg=COLOR_HEADER_FG,
                  font=("Segoe UI", 9), relief=tk.FLAT, padx=6,
                  command=self._pick_custom).grid(row=2, column=0, columnspan=6,
                                                   sticky=tk.EW, pady=(6, 0))

        # --- Dialog Action Buttons (OK / Cancel) ---
        btn_frame = tk.Frame(self.window, bg=COLOR_HEADER_BG)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=16)

        # Cancel button closes the modal without saving changes
        tk.Button(btn_frame, text="Cancel", command=self.window.destroy,
                  bg="#3a4a5a", fg=COLOR_HEADER_FG, font=("Segoe UI", 10),
                  width=10, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        # OK button validates inputs and saves configuration
        tk.Button(btn_frame, text="OK", command=self._ok, bg="#2a7f37",
                  fg="#ffffff", font=("Segoe UI", 10), width=10,
                  relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        # Allow inputs column to stretch horizontally to match borders
        self.window.columnconfigure(1, weight=1)
        # Establish parent window relationship so subwindow appears centered over parent
        self.window.transient(parent)
        # Grab window focus so users must close this dialog before interacting with main app window
        self.window.grab_set()

    def _pick_preset(self, hex_c: str) -> None:
        """Update active color preview and visual button states."""
        self.selected_color = hex_c
        # Update background color of preview box
        self.preview.configure(bg=hex_c)
        # Toggle border styling: sunken for chosen color, flat/raised for others
        for btn, c in self.color_btns:
            btn.configure(bd=3 if c == hex_c else 1,
                          relief=tk.SUNKEN if c == hex_c else tk.RAISED)

    def _pick_custom(self) -> None:
        """Launch system color selection window."""
        result = colorchooser.askcolor(initialcolor=self.selected_color,
                                       title="Choose Section Color")
        if result and result[1]:
            # Apply selected color from color selection dialog output
            self._pick_preset(result[1])

    def _ok(self) -> None:
        """Validate input field contents and record choices."""
        name = self.name_entry.get().strip()
        # Verify name is not left empty
        if not name:
            messagebox.showerror("Validation Error", "Section name is required.")
            return
        # Store result tuple containing section details
        self.result = (name, self.selected_color)
        # Close the dialog window
        self.window.destroy()


class MachineEditorDialog:
    """Dialog for editing a single machine (name + IP only)."""

    def __init__(self, parent, machine: Machine | None = None) -> None:
        self.result = None
        # Create a new top-level subwindow
        self.window = tk.Toplevel(parent)
        # Custom title based on operation
        self.window.title("Edit Machine" if machine else "Add Machine")
        self.window.geometry("420x180")
        self.window.configure(bg=COLOR_HEADER_BG)
        self.window.resizable(False, False)

        # Machine Name Label & Entry
        tk.Label(self.window, text="Machine Name:", bg=COLOR_HEADER_BG,
                 fg=COLOR_HEADER_FG, font=("Segoe UI", 10)
                 ).grid(row=0, column=0, sticky=tk.W, padx=16, pady=12)
        self.name_entry = tk.Entry(self.window, font=("Segoe UI", 11), width=28)
        self.name_entry.grid(row=0, column=1, sticky=tk.EW, padx=16, pady=12)
        if machine:
            self.name_entry.insert(0, machine.name)

        # IP Address Label & Entry
        tk.Label(self.window, text="IP Address:", bg=COLOR_HEADER_BG,
                 fg=COLOR_HEADER_FG, font=("Segoe UI", 10)
                 ).grid(row=1, column=0, sticky=tk.W, padx=16, pady=12)
        self.ip_entry = tk.Entry(self.window, font=("Segoe UI", 11), width=28)
        self.ip_entry.grid(row=1, column=1, sticky=tk.EW, padx=16, pady=12)
        if machine:
            self.ip_entry.insert(0, machine.ip)

        # Action Buttons frame
        bf = tk.Frame(self.window, bg=COLOR_HEADER_BG)
        bf.grid(row=2, column=0, columnspan=2, pady=12)
        # Cancel Button
        tk.Button(bf, text="Cancel", command=self.window.destroy, bg="#3a4a5a",
                  fg=COLOR_HEADER_FG, font=("Segoe UI", 10), width=10,
                  relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        # OK Button
        tk.Button(bf, text="OK", command=self._ok, bg="#2a7f37", fg="#ffffff",
                  font=("Segoe UI", 10), width=10, relief=tk.FLAT
                  ).pack(side=tk.LEFT, padx=5)

        # Configure geometry management behavior
        self.window.columnconfigure(1, weight=1)
        self.window.transient(parent)
        self.window.grab_set()

    def _ok(self) -> None:
        """Validate name and IP are filled out before returning result."""
        name = self.name_entry.get().strip()
        ip = self.ip_entry.get().strip()
        if not name or not ip:
            messagebox.showerror("Validation Error", "Name and IP are required.")
            return
        # Store result tuple and close dialog
        self.result = (name, ip)
        self.window.destroy()


class MachinesEditorWindow:
    """Window for editing machines with drag-and-drop sections."""

    # Set up keys referencing column identifiers in Treeview
    DATA_COLS = ("ip", "status", "last_seen", "last_check")

    def __init__(self, parent: tk.Tk, monitor: NetworkMonitor) -> None:
        self.monitor = monitor
        # Work with an independent copy of machines to support canceling edits cleanly
        self.machines: list[Machine] = monitor.get_machines_copy()
        # State tracker to know if any changes were made
        self.edited = False
        # Search query string used to filter table contents
        self.search_query = ""

        # Load list of ordered sections
        self._load_sections()

        # Drag state tracking variables
        self._drag_item = None          # Refers to the Treeview item id currently clicked
        self._drag_start_y = 0          # Tracks coordinate of initial mouse down
        self._dragging = False          # Becomes True once mouse moves past threshold
        self._iid_to_machine: dict[str, Machine] = {}   # Maps tree row ids to Machine objects
        self._iid_to_section: dict[str, dict] = {}      # Maps tree row ids to section dicts

        # Create main editor modal window
        self.window = tk.Toplevel(parent)
        self.window.title("Edit Machines — Sections & Drag-and-Drop")
        self.window.geometry("1100x600")
        self.window.minsize(850, 450)
        self.window.configure(bg=COLOR_HEADER_BG)

        # Make window transient relative to parent
        self.window.transient(parent)
        # Lock GUI focus to prevent interacting with the main workspace before closing this window
        self.window.grab_set()

        def _on_click_outside(event):
            """Listen to clicks outside modal dialog to play warning bells."""
            if event.widget == self.window:
                x, y = event.x_root, event.y_root
                x0 = self.window.winfo_rootx()
                y0 = self.window.winfo_rooty()
                x1 = x0 + self.window.winfo_width()
                y1 = y0 + self.window.winfo_height()
                # If click lands outside current window coordinates, trigger OS notification alert
                if not (x0 <= x <= x1 and y0 <= y <= y1):
                    self.window.bell()
                    
        # Bind mouse clicks to warning notification callback
        self.window.bind("<ButtonPress>", _on_click_outside)

        # Setup modern dark design styles for Treeview component
        style = ttk.Style(self.window)
        style.theme_use("clam")
        style.configure("Treeview", background=COLOR_ROW_BG,
                         foreground=COLOR_HEADER_FG, fieldbackground=COLOR_ROW_BG,
                         rowheight=32, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=COLOR_HEADER_BG,
                         foreground=COLOR_HEADER_FG, font=("Segoe UI", 10, "bold"))
        style.map("Treeview.Heading", background=[("active", "#313244")], foreground=[("active", "#ffffff")])
        style.map("Treeview", background=[("selected", "#45475a")])

        # Build dialog interface widgets
        self._build_ui()

    # ------------------------------------------------------------------ #
    # Section data helpers                                                 #
    # ------------------------------------------------------------------ #

    def _load_sections(self) -> None:
        """Build ordered sections list from sections.json + machines."""
        raw = load_sections()
        self.sections: list[dict] = []
        seen = set()
        
        # Add sections defined in sections.json file first
        for s in raw:
            name = s.get("name", "Default")
            if name not in seen:
                self.sections.append({"name": name, "color": s.get("color", "#4a5a7a")})
                seen.add(name)
                
        # Ensure that any section referenced in active machines exists in layout lists
        for m in self.machines:
            sec = m.section or "Default"
            if sec not in seen:
                self.sections.append({"name": sec, "color": "#4a5a7a"})
                seen.add(sec)
                
        # Ensure that fallback 'Default' section exists
        if "Default" not in seen:
            self.sections.insert(0, {"name": "Default", "color": "#4a5a7a"})

    def _section_color(self, name: str) -> str:
        """Find color mapping for a section by name."""
        for s in self.sections:
            if s["name"] == name:
                return s["color"]
        return "#4a5a7a"

    def _save_sections(self) -> None:
        """Write current sections layout order and custom colors to configuration file."""
        save_sections(self.sections)

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        """Create and place Tkinter widget controls in window layout."""
        # --- Search Bar Frame ---
        sf = tk.Frame(self.window, bg=COLOR_HEADER_BG, pady=6, padx=16)
        sf.pack(fill=tk.X)
        tk.Label(sf, text="🔍 Search:", bg=COLOR_HEADER_BG, fg=COLOR_HEADER_FG,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        # Bind keyboard typing to automatically filter table items
        self.search_var.trace("w", lambda *_: self._on_search())
        tk.Entry(sf, textvariable=self.search_var, width=35,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        # Clear search button
        tk.Button(sf, text="✕", command=lambda: self.search_var.set(""),
                  bg="#3a4a5a", fg=COLOR_HEADER_FG, font=("Segoe UI", 9),
                  relief=tk.FLAT, padx=6).pack(side=tk.LEFT, padx=3)

        # --- Toolbar Controls Frame ---
        tb = tk.Frame(self.window, bg=COLOR_HEADER_BG, pady=6, padx=16)
        tb.pack(fill=tk.X)

        # Generate action buttons (add sections, machines, edit, delete)
        for text, cmd, bg in [
            ("+ Section", self._add_section, "#5a4a7a"),
            ("+ Machine", self._add_machine, "#2a7f37"),
            ("✎ Edit", self._edit_selected, "#1e5a96"),
            ("✕ Delete", self._delete_selected, "#c41e3a"),
        ]:
            tk.Button(tb, text=text, command=cmd, bg=bg, fg="#ffffff",
                      font=("Segoe UI", 10), padx=10, relief=tk.FLAT
                      ).pack(side=tk.LEFT, padx=3)

        # Display helper instruction label
        tk.Label(tb, text="⇅ Drag rows to reorder", bg=COLOR_HEADER_BG,
                 fg="#666677", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=12)

        # Save and Close action button
        tk.Button(tb, text="💾 Save & Close", command=self._save_and_close,
                  bg="#3a7f37", fg="#ffffff", font=("Segoe UI", 10, "bold"),
                  padx=10, relief=tk.FLAT).pack(side=tk.RIGHT, padx=3)

        # --- Table Treeview Container ---
        container = tk.Frame(self.window, bg=COLOR_HEADER_BG, padx=16, pady=6)
        container.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(container, columns=self.DATA_COLS,
                                  show="tree headings", selectmode="browse")

        # Configure columns header texts and spacing
        self.tree.heading("#0", text="Name", anchor=tk.W)
        self.tree.column("#0", width=220, stretch=True)
        col_info = [("ip", "IP Address", 140), ("status", "Status", 80),
                     ("last_seen", "Last Seen", 130), ("last_check", "Last Check", 130)]
        for cid, label, w in col_info:
            self.tree.heading(cid, text=label)
            anc = tk.CENTER
            self.tree.column(cid, width=w, anchor=anc)

        # Scrollbar integration
        vsb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure highlighted row feedback during drag and drop hover
        self.tree.tag_configure("drop_highlight", background="#3a6a9a")

        # Drag and drop mouse event bindings
        self.tree.bind("<ButtonPress-1>", self._on_press)
        self.tree.bind("<B1-Motion>", self._on_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_release)
        # Bind double-clicking to trigger direct row edits
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        # Status Bar Info Panel
        self.status_label = tk.Label(self.window, text="", font=("Segoe UI", 9),
                                      bg=COLOR_HEADER_BG, fg="#888899",
                                      anchor=tk.W, padx=16, pady=6)
        self.status_label.pack(fill=tk.X)

        # Initial loading sweep of inventory rows
        self._refresh_table()

    # ------------------------------------------------------------------ #
    # Table refresh                                                        #
    # ------------------------------------------------------------------ #

    def _on_search(self) -> None:
        """Triggered automatically when text is typed in search box."""
        self.search_query = self.search_var.get().lower().strip()
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Clear and redraw all section folders and machine rows based on filters and orders."""
        # Wipe all items out of Treeview first
        for item in self.tree.get_children():
            self.tree.delete(item)
        # Clear state translation mappings
        self._iid_to_machine.clear()
        self._iid_to_section.clear()

        # Apply search string filter to machines inventory list
        if self.search_query:
            filtered = [m for m in self.machines
                        if self.search_query in m.name.lower()
                        or self.search_query in m.ip.lower()]
        else:
            filtered = self.machines

        # Group machines list by their respective sections
        groups: dict[str, list[Machine]] = {}
        for m in filtered:
            sec = m.section or "Default"
            groups.setdefault(sec, []).append(m)

        # Insert sections in stored order sequence
        m_counter = 0
        for sec_dict in self.sections:
            sec_name = sec_dict["name"]
            sec_machines = groups.get(sec_name, [])

            # Don't show empty sections during searches
            if self.search_query and not sec_machines:
                continue

            # Assign color and style formatting tags
            color = sec_dict["color"]
            tag = f"sec_{id(sec_dict)}"
            self.tree.tag_configure(tag, background=color, foreground="#ffffff",
                                    font=("Segoe UI", 11, "bold"))

            # Insert parent section directory row
            sec_iid = f"S{id(sec_dict)}"
            self.tree.insert("", tk.END, iid=sec_iid,
                             text=f"  ■  {sec_name}",
                             values=("", "", "", "", ""),
                             open=True, tags=(tag,))
            # Store reference mapping to the section configuration dict
            self._iid_to_section[sec_iid] = sec_dict

            # Insert corresponding child machines under their section folder
            for machine in sorted(sec_machines, key=lambda m: m.name):
                seen = machine.last_seen.strftime("%Y-%m-%d %H:%M:%S") if machine.last_seen else "—"
                chk = machine.last_check.strftime("%H:%M:%S") if machine.last_check else "—"

                m_iid = f"M{m_counter}"
                m_counter += 1
                # Nest row inside parent section using sec_iid
                self.tree.insert(sec_iid, tk.END, iid=m_iid,
                                 text=f"  {machine.name}",
                                 values=(machine.ip, machine.status.value, seen, chk))
                # Store lookup mapping to active Machine object
                self._iid_to_machine[m_iid] = machine

        # Update status labels depending on search state
        total = len(self.machines)
        shown = len(filtered)
        n_sec = len([s for s in self.sections if groups.get(s["name"])])
        if self.search_query:
            self.status_label.configure(
                text=f"Showing {shown}/{total} machines  |  Search: '{self.search_query}'")
        else:
            self.status_label.configure(
                text=f"Total: {total} machines in {n_sec} section(s)  |  "
                     f"Drag sections ⇅ to reorder  •  Drag machines into sections")

    # ------------------------------------------------------------------ #
    # Drag-and-drop                                                        #
    # ------------------------------------------------------------------ #

    def _on_press(self, event) -> None:
        """Record the clicked item and starting coordinate on left-click down."""
        self._drag_item = self.tree.identify_row(event.y)
        self._drag_start_y = event.y
        self._dragging = False

    def _on_motion(self, event) -> None:
        """Track drag distance and display hand cursor once past threshold."""
        if not self._drag_item:
            return
        # If user drags further than 8 pixels, initiate drag feedback
        if not self._dragging and abs(event.y - self._drag_start_y) > 8:
            self._dragging = True
            # Change mouse cursor style
            self.tree.configure(cursor="hand2")

        if not self._dragging:
            return

        # Dynamically highlight active hover rows to help visualize drops
        target = self.tree.identify_row(event.y)
        if target and target != self._drag_item:
            self.tree.selection_set(target)

    def _on_release(self, event) -> None:
        """Trigger reorder or swap logic when click is released."""
        if self._dragging and self._drag_item:
            target = self.tree.identify_row(event.y)
            # Make sure we dropped over a valid target
            if target and target != self._drag_item:
                self._perform_drop(self._drag_item, target)
        self._dragging = False
        self._drag_item = None
        # Restore default cursor shape
        self.tree.configure(cursor="")

    def _perform_drop(self, drag_iid: str, drop_iid: str) -> None:
        """Evaluate targets and rearrange items list."""
        drag_is_section = drag_iid in self._iid_to_section
        drop_is_section = drop_iid in self._iid_to_section

        if drag_is_section:
            # Case A: Reordering entire section blocks
            drop_section = self._iid_to_section.get(drop_iid)
            if not drop_is_section:
                # If dropped over child machine, retrieve its parent section block
                parent_iid = self.tree.parent(drop_iid)
                drop_section = self._iid_to_section.get(parent_iid)
            if not drop_section:
                return

            drag_section = self._iid_to_section[drag_iid]
            if drag_section is drop_section:
                return

            # Reorder section within list and update treeview
            self.sections.remove(drag_section)
            new_idx = self.sections.index(drop_section)
            self.sections.insert(new_idx, drag_section)
            self.edited = True
            self._refresh_table()

        elif drag_iid in self._iid_to_machine:
            # Case B: Reassigning machines to different sections
            if drop_is_section:
                target_sec = self._iid_to_section[drop_iid]
            else:
                parent_iid = self.tree.parent(drop_iid)
                target_sec = self._iid_to_section.get(parent_iid)
            if not target_sec:
                return

            machine = self._iid_to_machine[drag_iid]
            # Cancel operation if dropped in current section
            if machine.section == target_sec["name"]:
                return

            # Update machine section string reference
            machine.section = target_sec["name"]
            self.edited = True
            self._refresh_table()

    # ------------------------------------------------------------------ #
    # CRUD operations                                                      #
    # ------------------------------------------------------------------ #

    def _add_section(self) -> None:
        """Open SectionEditorDialog to create a new category section."""
        dlg = SectionEditorDialog(self.window)
        self.window.wait_window(dlg.window)
        if dlg.result:
            name, color = dlg.result
            # Stop user from creating sections with identical names
            if any(s["name"] == name for s in self.sections):
                messagebox.showwarning("Duplicate", f"Section '{name}' already exists.")
                return
            self.sections.append({"name": name, "color": color})
            self.edited = True
            self._refresh_table()

    def _add_machine(self) -> None:
        """Create new machine and assign to selected section automatically."""
        # Find default target section from the current selection
        target_section = "Default"
        sel = self.tree.selection()
        if sel:
            iid = sel[0]
            if iid in self._iid_to_section:
                target_section = self._iid_to_section[iid]["name"]
            elif iid in self._iid_to_machine:
                target_section = self._iid_to_machine[iid].section or "Default"

        dlg = MachineEditorDialog(self.window)
        self.window.wait_window(dlg.window)
        if dlg.result:
            name, ip = dlg.result
            # Add new machine details to active inventory list
            self.machines.append(Machine(name=name, ip=ip, section=target_section))
            self.edited = True
            self._refresh_table()

    def _edit_selected(self) -> None:
        """Trigger section color picker or machine details editor based on selection."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an item to edit.")
            return
        iid = sel[0]

        if iid in self._iid_to_section:
            # Edit existing section details
            sec = self._iid_to_section[iid]
            dlg = SectionEditorDialog(self.window, name=sec["name"], color=sec["color"])
            self.window.wait_window(dlg.window)
            if dlg.result:
                new_name, new_color = dlg.result
                old_name = sec["name"]
                # Update all machines references belonging to this section name
                if new_name != old_name:
                    for m in self.machines:
                        if m.section == old_name:
                            m.section = new_name
                sec["name"] = new_name
                sec["color"] = new_color
                self.edited = True
                self._refresh_table()

        elif iid in self._iid_to_machine:
            # Edit existing machine details
            machine = self._iid_to_machine[iid]
            dlg = MachineEditorDialog(self.window, machine)
            self.window.wait_window(dlg.window)
            if dlg.result:
                machine.name, machine.ip = dlg.result
                self.edited = True
                self._refresh_table()

    def _delete_selected(self) -> None:
        """Delete section or machine from active monitoring lists."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an item to delete.")
            return
        iid = sel[0]

        if iid in self._iid_to_section:
            # Prevent deletion of fallback 'Default' section
            sec = self._iid_to_section[iid]
            name = sec["name"]
            if name == "Default":
                messagebox.showwarning("Cannot Delete", "Cannot delete the Default section.")
                return
            # Inform users if child machines will be migrated
            child_count = sum(1 for m in self.machines if m.section == name)
            msg = f"Delete section '{name}'?"
            if child_count:
                msg += f"\n{child_count} machine(s) will be moved to Default."
            if messagebox.askyesno("Confirm Delete", msg):
                # Update child machines section to Default fallback category
                for m in self.machines:
                    if m.section == name:
                        m.section = "Default"
                self.sections.remove(sec)
                self.edited = True
                self._refresh_table()

        elif iid in self._iid_to_machine:
            # Delete selected machine row
            machine = self._iid_to_machine[iid]
            if messagebox.askyesno("Confirm Delete",
                                    f"Delete machine '{machine.name}' ({machine.ip})?"):
                self.machines.remove(machine)
                self.edited = True
                self._refresh_table()

    def _save_and_close(self) -> None:
        """Flush changes to inventory text files and sections database, then destroy dialog."""
        if self.edited:
            # Save section colors and sorting orders
            self._save_sections()
            # Push updated machines list to the network monitor engine
            self.monitor.update_machines(self.machines)
            messagebox.showinfo("Success", "Machines and sections saved!")
        self.window.destroy()
