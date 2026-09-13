import json, queue, threading, time
import serial
from pathlib import Path
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from serial.tools import list_ports
from .controller import Bus
from .profiles import PROFILES
from .storage import data_directory, load_poses, save_poses
import sys

BG = "#edf1f6"
NAVY = "#12233e"
BLUE = "#2563eb"
INK = "#172b48"
MUTED = "#60718b"


class App:
    def __init__(self, root):
        self.root = root
        self.bus = Bus()
        self.connected = False
        self.busy = False
        self.closing = False
        self.rows = {}
        self.jobs = queue.Queue()
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.pending_release = None
        self.history = {}
        self.last_poll = 0
        self.loading = False
        self.busy_kind = None
        self.pending_action = None
        self.want_connection = False
        self.last_reconnect = 0
        self.last_discovery = 0
        self.link_identity = None
        self.link_path = ""
        self.link_baud = 1000000
        self.editor_dirty = False
        self.editor_selection = ()
        self.store = data_directory() / "poses.json"
        self.poses = load_poses(self.store)
        root.title("TTL Servo Studio")
        root.geometry("1180x860")
        root.minsize(1100, 820)
        root.configure(bg=BG)
        st = ttk.Style()
        st.theme_use("clam")
        st.configure(".", font=("Helvetica", 12), foreground=INK)
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG)
        st.configure("TButton", padding=(12, 8), background="white", borderwidth=0)
        st.map(
            "TButton",
            background=[("active", "#dbeafe")],
            foreground=[("disabled", "#9aa6b6")],
        )
        st.configure("Primary.TButton", background=BLUE, foreground="white")
        st.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8"), ("disabled", "#a3b8de")],
            foreground=[("disabled", "white")],
        )
        st.configure("Release.TButton", background="#fee2e2", foreground="#991b1b")
        st.configure(
            "Treeview",
            rowheight=38,
            background="white",
            fieldbackground="white",
            borderwidth=0,
        )
        st.configure(
            "Treeview.Heading",
            font=("Helvetica", 11, "bold"),
            background="#e4ebf5",
            padding=8,
        )
        st.map(
            "Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", INK)],
        )
        st.configure("TCheckbutton", background=BG)
        head = tk.Frame(root, bg=NAVY, padx=24, pady=18)
        head.pack(fill="x")
        icon = tk.Canvas(head, width=48, height=48, bg=NAVY, highlightthickness=0)
        icon.pack(side="left", padx=(0, 12))
        icon.create_arc(
            5, 3, 43, 41, start=-45, extent=270, style="arc", outline="#5eead4", width=4
        )
        icon.create_line(24, 22, 35, 11, fill="white", width=4)
        icon.create_oval(20, 18, 28, 26, fill="white", outline="white")
        icon.create_line(
            5,
            45,
            15,
            45,
            15,
            38,
            25,
            38,
            25,
            45,
            35,
            45,
            35,
            38,
            44,
            38,
            fill="#60a5fa",
            width=2,
        )
        tk.Label(
            head,
            text="TTL Servo Studio",
            font=("Helvetica", 25, "bold"),
            bg=NAVY,
            fg="white",
        ).pack(side="left")
        tk.Label(
            head,
            text="Created by Mehrdad Farimani",
            font=("Helvetica", 11),
            bg=NAVY,
            fg="#a8bbd9",
        ).pack(side="left", padx=24)
        self.badge = tk.Label(
            head,
            text="●  OFFLINE",
            bg=NAVY,
            fg="#a8bbd9",
            font=("Helvetica", 11, "bold"),
        )
        self.badge.pack(side="right")
        body = ttk.Frame(root, padding=(24, 16))
        body.pack(fill="both", expand=True)
        conn = ttk.Frame(body)
        conn.pack(fill="x")
        self.port = tk.StringVar()
        self.baud = tk.StringVar(value="1000000")
        self.portbox = ttk.Combobox(
            conn, textvariable=self.port, width=33, state="readonly"
        )
        self.portbox.pack(side="left")
        self.refresh = ttk.Button(conn, text="↻ Ports", command=self.refresh_ports)
        self.refresh.pack(side="left", padx=6)
        ttk.Label(conn, text="Baud").pack(side="left", padx=(8, 4))
        self.baudbox = ttk.Combobox(
            conn,
            textvariable=self.baud,
            values=[
                "1000000",
                "500000",
                "250000",
                "128000",
                "115200",
                "57600",
                "38400",
            ],
            width=10,
            state="readonly",
        )
        self.baudbox.pack(side="left")
        self.connectbtn = ttk.Button(
            conn, text="Connect", style="Primary.TButton", command=self.connect
        )
        self.connectbtn.pack(side="left", padx=8)
        self.live = tk.BooleanVar(value=True)
        ttk.Checkbutton(conn, text="Live readings", variable=self.live).pack(
            side="right"
        )
        ttk.Label(
            body,
            text="1  Connect USB + external servo power     2  Find servos and choose models     3  Prepare targets, then Move",
            foreground=MUTED,
        ).pack(anchor="w", pady=(10, 15))
        toolbar = ttk.Frame(body)
        toolbar.pack(fill="x", pady=(0, 9))
        self.scanbtn = ttk.Button(
            toolbar, text="Find servos (0–20)", command=lambda: self.scan(False)
        )
        self.scanbtn.pack(side="left")
        self.fullbtn = ttk.Button(
            toolbar, text="Full scan", command=lambda: self.scan(True)
        )
        self.fullbtn.pack(side="left", padx=6)
        self.cancelbtn = ttk.Button(toolbar, text="Cancel", command=self.cancel.set)
        self.cancelbtn.pack(side="left")
        ttk.Button(
            toolbar,
            text="Select all",
            command=lambda: self.tree.selection_set(self.tree.get_children()),
        ).pack(side="right")
        ttk.Label(toolbar, text="⌘-click to select several", foreground=MUTED).pack(
            side="right", padx=12
        )
        columns = (
            "id",
            "model",
            "position",
            "target",
            "speed",
            "actual",
            "voltage",
            "temp",
            "torque",
            "status",
        )
        table = ttk.Frame(body)
        table.pack(fill="x")
        self.tree = ttk.Treeview(
            table, columns=columns, show="headings", height=5, selectmode="extended"
        )
        for col, title, width in zip(
            columns,
            [
                "Servo",
                "Model",
                "Position",
                "Target",
                "Set speed",
                "Actual speed",
                "Supply",
                "Temp",
                "Torque",
                "Status",
            ],
            [60, 145, 85, 85, 80, 85, 65, 55, 60, 115],
        ):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="center", stretch=col == "status")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="x", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.selection_changed)
        self.tree.tag_configure("error", foreground="#b42318")
        self.tree.tag_configure("ok", foreground=INK)
        modelrow = ttk.Frame(body)
        modelrow.pack(fill="x", pady=(10, 0))
        ttk.Label(modelrow, text="Model for selected servos").pack(side="left")
        self.model = tk.StringVar(value="Choose model")
        self.modelbox = ttk.Combobox(
            modelrow,
            textvariable=self.model,
            values=[p.label for p in PROFILES.values()],
            state="readonly",
            width=26,
        )
        self.modelbox.pack(side="left", padx=8)
        ttk.Button(modelrow, text="Assign model", command=self.assign_model).pack(
            side="left"
        )
        ttk.Button(modelrow, text="Setup help", command=self.help).pack(side="right")
        mid = ttk.Frame(body)
        mid.pack(fill="both", expand=True, pady=(18, 12))
        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True, padx=(0, 22))
        right = ttk.Frame(mid)
        right.pack(side="right", fill="both", expand=True)
        self.selectiontext = tk.StringVar(value="Select a servo to prepare a move")
        ttk.Label(
            left, textvariable=self.selectiontext, font=("Helvetica", 15, "bold")
        ).pack(anchor="w")
        self.angle = tk.DoubleVar(value=150)
        self.speed = tk.StringVar(value="150")
        self.targetlabel = tk.StringVar(value="150.0°  ·  511 steps")
        ttk.Label(
            left, textvariable=self.targetlabel, font=("Helvetica", 24, "bold")
        ).pack(anchor="w", pady=(12, 2))
        self.slider = ttk.Scale(
            left, from_=0, to=300, variable=self.angle, command=self.angle_changed
        )
        self.slider.pack(fill="x")
        exact = ttk.Frame(left)
        exact.pack(fill="x", pady=8)
        ttk.Label(exact, text="Angle °").pack(side="left")
        self.anglebox = ttk.Spinbox(
            exact,
            from_=0,
            to=300,
            increment=1,
            textvariable=self.angle,
            width=7,
            command=self.angle_changed,
        )
        self.anglebox.pack(side="left", padx=6)
        self.anglebox.bind("<KeyRelease>", self.angle_changed)
        ttk.Label(exact, text="Speed (steps/s)").pack(side="left", padx=(12, 5))
        self.speedbox = ttk.Spinbox(
            exact, from_=1, to=1500, increment=25, textvariable=self.speed, width=7
        )
        self.speedbox.pack(side="left")
        self.angle.trace_add("write", self.edited)
        self.speed.trace_add("write", self.edited)
        actions = ttk.Frame(left)
        actions.pack(fill="x", pady=5)
        self.applybtn = ttk.Button(
            actions, text="Apply to selected targets", command=self.apply
        )
        self.applybtn.pack(side="left")
        self.centerbtn = ttk.Button(actions, text="Center target", command=self.center)
        self.centerbtn.pack(side="left", padx=6)
        ttk.Label(
            left,
            text="Edits only prepare targets. Click Move selected to send.\nSpeed 150 ≈ 44°/s. Different speeds can finish at different times.",
            foreground=MUTED,
            font=("Helvetica", 10),
        ).pack(anchor="w", pady=(7, 0))
        ttk.Label(right, text="Position history", font=("Helvetica", 15, "bold")).pack(
            anchor="w"
        )
        self.graph = tk.Canvas(right, height=125, bg="white", highlightthickness=0)
        self.graph.pack(fill="both", expand=True, pady=(10, 6))
        self.graph.bind("<Configure>", lambda e: self.draw_graph())
        self.detail = tk.StringVar(
            value="Live data appears after connection and discovery."
        )
        ttk.Label(
            right,
            textvariable=self.detail,
            foreground=MUTED,
            wraplength=460,
            font=("Helvetica", 10),
        ).pack(anchor="w")
        poses = ttk.Frame(body)
        poses.pack(fill="x", pady=(0, 12))
        ttk.Label(
            poses, text="POSES", font=("Helvetica", 10, "bold"), foreground=MUTED
        ).pack(side="left", padx=(0, 12))
        self.pose = tk.StringVar()
        self.posebox = ttk.Combobox(
            poses,
            textvariable=self.pose,
            values=sorted(self.poses),
            state="readonly",
            width=23,
        )
        self.posebox.pack(side="left")
        ttk.Button(poses, text="Save targets…", command=self.save_pose).pack(
            side="left", padx=6
        )
        ttk.Button(poses, text="Load targets", command=self.load_pose).pack(side="left")
        ttk.Label(
            poses,
            text="Loading never moves servos",
            foreground=MUTED,
            font=("Helvetica", 10),
        ).pack(side="left", padx=12)
        bottom = ttk.Frame(body)
        bottom.pack(fill="x")
        self.movebtn = ttk.Button(
            bottom, text="▶  Move selected", style="Primary.TButton", command=self.move
        )
        self.movebtn.pack(side="left")
        self.readbtn = ttk.Button(bottom, text="Read now", command=self.read_now)
        self.readbtn.pack(side="left", padx=8)
        self.releasebtn = ttk.Button(
            bottom, text="Release selected", command=lambda: self.release(False)
        )
        self.releasebtn.pack(side="right")
        self.releaseall = ttk.Button(
            bottom,
            text="■  Release all found",
            style="Release.TButton",
            command=lambda: self.release(True),
        )
        self.releaseall.pack(side="right", padx=8)
        self.connection_note = tk.StringVar(
            value="USB and servo power are monitored separately."
        )
        ttk.Label(
            body,
            textvariable=self.connection_note,
            foreground=MUTED,
            font=("Helvetica", 10),
        ).pack(anchor="w", pady=(8, 0))
        self.status = tk.StringVar(
            value="Connect your adapter. Servos are discovered automatically; no movement on connect."
        )
        ttk.Label(
            body,
            textvariable=self.status,
            wraplength=1020,
            foreground=MUTED,
            font=("Helvetica", 11),
        ).pack(anchor="w", pady=(12, 0))
        self.refresh_ports()
        self.controls()
        threading.Thread(target=self.worker, daemon=True).start()
        root.after(60, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def assign_model(self):
        key = next(
            (key for key, p in PROFILES.items() if p.label == self.model.get()), None
        )
        if key is None or not self.selected():
            self.status.set("Select servo rows and choose their exact model.")
            return
        for sid in self.selected():
            self.rows[sid]["profile"] = key
            self.render(sid)
        self.controls()
        self.status.set(
            PROFILES[key].label
            + " assigned locally. "
            + PROFILES[key].validation
            + " No servo settings changed."
        )

    def help(self):
        messagebox.showinfo(
            "Setup & supported servos",
            "Use a TTL half-duplex USB bus-servo adapter, not a plain USB UART.\n"
            "For Waveshare Adapter (A), set both jumpers to B.\n"
            "Supply regulated 5 V externally for the supported models. USB alone does not power the servos.\n\n"
            "SC09: hardware-tested. SCS0009: profile based on manufacturer specifications; hardware validation pending.\n"
            "Choose the exact model for each row before movement. Profiles are local and do not change firmware.\n\n"
            "Each servo needs a unique ID. Identical factory IDs can corrupt replies; connect one servo at a time to configure IDs with the manufacturer tool.\n"
            "PWM, RS485, STS and other unlisted servos are not supported.\n\n"
            "Powerbank off? Wake it; live reads recover, but movements are never replayed.\n"
            "Release torque can let attached loads fall. Disconnecting does not release torque.",
            parent=self.root,
        )

    def selected(self):
        return [int(x) for x in self.tree.selection()]

    def refresh_ports(self):
        ports = sorted(
            p.device
            for p in list_ports.comports()
            if not (sys.platform == "darwin" and p.device.startswith("/dev/tty."))
            and "Bluetooth" not in p.device
        )
        self.portbox["values"] = ports
        if self.port.get() not in ports:
            self.port.set(ports[0] if ports else "")

    def controls(self):
        available = not self.busy or self.busy_kind == "read"
        idle = self.connected and available and self.pending_action is None
        self.connectbtn.configure(
            text="Disconnect" if self.want_connection else "Connect",
            state="normal" if available else "disabled",
        )
        for w in (self.portbox, self.baudbox):
            w.configure(
                state="disabled" if self.want_connection or self.busy else "readonly"
            )
        self.refresh.configure(
            state="disabled" if self.want_connection or self.busy else "normal"
        )
        for w in (self.scanbtn, self.fullbtn, self.readbtn):
            w.configure(state="normal" if idle else "disabled")
        self.cancelbtn.configure(state="normal" if self.busy else "disabled")
        selected = self.selected()
        valid = selected and all(
            self.rows[i].get("ok") and self.rows[i].get("profile") in PROFILES
            for i in selected
        )
        self.movebtn.configure(
            state="normal" if idle and valid and not self.editor_dirty else "disabled"
        )
        for w in (
            self.applybtn,
            self.centerbtn,
            self.slider,
            self.anglebox,
            self.speedbox,
        ):
            w.configure(state="normal" if selected else "disabled")
        self.releasebtn.configure(
            state="normal" if self.connected and selected else "disabled"
        )
        self.releaseall.configure(
            state="normal" if self.connected and self.rows else "disabled"
        )
        ready = sum(bool(r.get("ok")) for r in self.rows.values())
        if not self.want_connection:
            label, color = "OFFLINE", "#a8bbd9"
        elif not self.connected:
            label, color = "RECONNECTING", "#fcd34d"
        elif self.rows and not ready:
            label, color = "WAITING FOR SERVOS", "#fcd34d"
        elif ready < len(self.rows):
            label, color = f"{ready}/{len(self.rows)} RESPONDING", "#fcd34d"
        elif ready:
            label, color = f"{ready} SERVOS READY", "#6ee7b7"
        else:
            label, color = "USB CONNECTED", "#a8bbd9"
        self.badge.configure(text="●  " + label, fg=color)
        if self.want_connection and not self.connected:
            note = "USB adapter lost. Retrying the same adapter every 3 seconds; no movement will be replayed."
        elif self.connected and self.rows and not ready:
            note = (
                "USB connected; servos are not replying. Restore servo power. Live readings retry automatically."
                if self.live.get()
                else "Servos are not replying. Restore power, then Read now or enable Live readings."
            )
        elif self.connected and not self.live.get():
            note = "Live readings paused. Table shows the last read; Read now refreshes it."
        elif self.connected:
            note = "Live readings active. Prepared targets are kept through power interruptions."
        else:
            note = "Disconnected. Closing this app does not switch off servo torque."
        self.connection_note.set(note)

    def submit(self, kind, fn, quiet=False):
        if self.closing:
            return
        if self.busy:
            if (
                self.busy_kind == "read"
                and kind != "read"
                and self.pending_action is None
            ):
                self.cancel.set()
                self.pending_action = (kind, fn, quiet)
                self.status.set("Finishing the current read…")
                self.controls()
            return
        self.busy = True
        self.busy_kind = kind
        self.cancel.clear()
        self.controls()
        if not quiet:
            self.status.set(
                {
                    "scan": "Searching for servos…",
                    "move": "Checking selected servos, then sending coordinated targets…",
                    "release": "Releasing torque…",
                    "reconnect": "Reconnecting USB adapter…",
                }.get(kind, "Working…")
            )
        self.jobs.put((kind, fn))

    def worker(self):
        while True:
            kind, fn = self.jobs.get()
            try:
                self.events.put((kind, fn(), None))
            except (serial.SerialException, OSError) as e:
                try:
                    self.bus.close()
                except Exception:
                    pass
                self.events.put(("link_lost", kind, str(e)))
            except Exception as e:
                self.events.put((kind, None, str(e)))

    def connect(self):
        if self.want_connection:
            self.want_connection = False
            self.pending_action = None
            self.pending_release = None
            self.submit("disconnect", self.bus.close)
            return
        if not self.port.get():
            self.status.set(
                "No USB serial adapter found. Plug it in and refresh ports."
            )
            return
        self.link_path = self.port.get()
        self.link_baud = int(self.baud.get())
        match = next(
            (p for p in list_ports.comports() if p.device == self.link_path), None
        )
        self.link_identity = (
            (match.vid, match.pid, match.serial_number)
            if match and match.serial_number
            else None
        )
        self.want_connection = True
        self.submit("connect", lambda: self.bus.open(self.link_path, self.link_baud))

    def reconnect(self):
        ports = list(list_ports.comports())
        if self.link_identity:
            match = next(
                (
                    p
                    for p in ports
                    if (p.vid, p.pid, p.serial_number) == self.link_identity
                ),
                None,
            )
        else:
            match = next((p for p in ports if p.device == self.link_path), None)
        if match is None:
            return
        self.link_path = match.device
        self.port.set(match.device)
        self.submit(
            "reconnect",
            lambda: self.bus.open(self.link_path, self.link_baud),
            quiet=True,
        )

    def scan(self, full=False):
        self.last_discovery = time.monotonic()

        def progress(n, total, found):
            self.events.put(
                ("progress", f"Scanned {n}/{total} IDs · {found} ready", None)
            )

        ids = list(range(254 if full else 21))
        self.scan_ids = set(ids)
        self.submit("scan", lambda: self.bus.scan(ids, self.cancel, progress))

    def snapshots(self, ids):
        out = {}
        for sid in ids:
            if self.cancel.is_set():
                break
            try:
                out[sid] = self.bus.snapshot(sid)
            except (serial.SerialException, OSError):
                raise
            except Exception as e:
                out[sid] = {"error": str(e)}
        return out

    def read_now(self):
        ids = list(self.rows)
        if ids:
            self.submit("read", lambda: self.snapshots(ids))
        else:
            self.scan()

    def update_rows(self, data):
        for sid, d in data.items():
            if sid not in self.rows:
                self.rows[sid] = {
                    "target": d.get("position", 511),
                    "set_speed": 150,
                    "profile": None,
                }
            row = self.rows[sid]
            if "error" in d:
                row.update(ok=False, error=d["error"])
                self.history[sid] = []
            else:
                row.update(d, ok=True, error="")
                self.history.setdefault(sid, []).append(
                    (time.monotonic(), d["position"])
                )
                self.history[sid] = self.history[sid][-120:]
            self.render(sid)
        if not self.selected() and self.rows:
            self.tree.selection_set(str(next(iter(self.rows))))
        ids = self.selected()
        if ids:
            r = self.rows[ids[0]]
            self.detail.set(
                r.get("error")
                or f'ID {ids[0]} · limits {r.get("low",0)}–{r.get("high",1023)} steps · readings updated live'
            )
        self.draw_graph()
        self.controls()

    def render(self, sid):
        r = self.rows[sid]
        ok = r.get("ok")
        fmt = lambda x: f"{x*300/1023:.1f}°"
        values = (
            f"ID {sid}",
            (
                PROFILES[r["profile"]].label
                if r.get("profile") in PROFILES
                else "Choose model"
            ),
            fmt(r["position"]) if ok else "—",
            fmt(r["target"]),
            f'{r["set_speed"]} /s',
            f'{r["speed"]} /s' if ok else "—",
            f'{r["voltage"]:.1f} V' if ok else "—",
            f'{r["temperature"]}°C' if ok else "—",
            ("Hold" if r["torque"] else "Free") if ok else "—",
            (
                ("Ready" if r.get("profile") in PROFILES else "Set model")
                if ok
                else "No reading"
            ),
        )
        if self.tree.exists(str(sid)):
            self.tree.item(str(sid), values=values, tags=("ok" if ok else "error",))
        else:
            self.tree.insert(
                "", "end", iid=str(sid), values=values, tags=("ok" if ok else "error",)
            )

    def selection_changed(self, *_):
        ids = self.selected()
        if tuple(ids) == self.editor_selection:
            return
        self.editor_selection = tuple(ids)
        self.editor_dirty = False
        self.loading = True
        if ids:
            row = self.rows[ids[0]]
            self.model.set(
                PROFILES[row["profile"]].label
                if row.get("profile") in PROFILES
                else "Choose model"
            )
            self.angle.set(round(row["target"] * 300 / 1023, 1))
            self.speed.set(str(row["set_speed"]))
            self.selectiontext.set("Prepare ID " + ", ".join(map(str, ids)))
            self.detail.set(
                row.get("error") or "Graph follows the first selected servo."
            )
        else:
            self.selectiontext.set("Select a servo to prepare a move")
        self.loading = False
        self.angle_changed()
        self.draw_graph()
        self.controls()

    def edited(self, *_):
        if self.loading:
            return
        self.editor_dirty = True
        if hasattr(self, "status"):
            self.status.set(
                "Unapplied edits — click Apply to selected targets before moving."
            )
        if hasattr(self, "movebtn"):
            self.controls()

    def angle_changed(self, *_):
        try:
            a = self.angle.get()
            self.targetlabel.set(f"{a:.1f}°  ·  {round(a*1023/300)} steps")
        except (tk.TclError, ValueError, OverflowError):
            pass

    def center(self):
        self.angle.set(round(511 * 300 / 1023, 1))
        self.angle_changed()
        self.apply()

    def apply(self):
        try:
            a = self.angle.get()
            speed = int(self.speed.get())
            if not 0 <= a <= 300 or not 1 <= speed <= 1500:
                raise ValueError()
            target = round(a * 1023 / 300)
            for sid in self.selected():
                r = self.rows[sid]
                if not r.get("low", 0) <= target <= r.get("high", 1023):
                    self.status.set(
                        f'ID {sid}: target must be within {r["low"]*300/1023:.1f}–{r["high"]*300/1023:.1f}°.'
                    )
                    return False
        except (ValueError, tk.TclError):
            self.status.set("Use angle 0–300° and speed 1–1500 steps/s.")
            return False
        for sid in self.selected():
            self.rows[sid].update(target=target, set_speed=speed)
            self.render(sid)
        self.editor_dirty = False
        self.controls()
        self.status.set("Targets prepared. No movement sent.")
        return True

    def move(self):
        if self.editor_dirty:
            self.status.set("Apply your edits before moving.")
            return
        ids = self.selected()
        if not ids or not all(self.rows[i].get("ok") for i in ids):
            return
        plans = {
            i: {
                "target": self.rows[i]["target"],
                "speed": self.rows[i]["set_speed"],
                "profile": self.rows[i].get("profile"),
            }
            for i in ids
        }
        self.submit("move", lambda: self.bus.move(plans, self.cancel))

    def release(self, all_found):
        ids = list(self.rows) if all_found else self.selected()
        if not ids:
            return
        self.pending_action = None
        if self.busy:
            self.cancel.set()
            self.pending_release = ids
            self.status.set("Cancelling current work; torque release is next.")
            return
        self.submit("release", lambda: self.bus.release(ids))

    def save_pose(self):
        if not self.rows:
            self.status.set("Find servos before saving targets.")
            return
        name = simpledialog.askstring(
            "Save pose", "Name for these targets:", parent=self.root
        )
        if not name:
            return
        self.poses[name] = {
            str(i): {"target": r["target"], "speed": r["set_speed"]}
            for i, r in self.rows.items()
        }
        try:
            save_poses(self.store, self.poses)
        except OSError as e:
            self.status.set(f"Could not save: {e}")
            return
        self.posebox["values"] = sorted(self.poses)
        self.pose.set(name)
        self.status.set(f"Saved “{name}”.")

    def load_pose(self):
        pose = self.poses.get(self.pose.get())
        applied = 0
        if not pose:
            self.status.set("Choose a saved pose.")
            return
        for key, p in pose.items():
            sid = int(key)
            if (
                sid in self.rows
                and 0 <= p["target"] <= 1023
                and 1 <= p["speed"] <= 1500
            ):
                self.rows[sid].update(target=p["target"], set_speed=p["speed"])
                self.render(sid)
                applied += 1
        self.editor_selection = ()
        self.selection_changed()
        self.status.set(
            f"Loaded {applied} targets. Select servos and click Move selected to send."
        )

    def draw_graph(self):
        c = self.graph
        c.delete("all")
        w = max(c.winfo_width(), 250)
        h = max(c.winfo_height(), 100)
        for deg in (0, 150, 300):
            y = h - 18 - deg / 300 * (h - 34)
            c.create_line(34, y, w - 12, y, fill="#e4ebf5")
            c.create_text(
                28, y, text=str(deg), anchor="e", fill=MUTED, font=("Helvetica", 9)
            )
        ids = self.selected()
        if not ids or len(self.history.get(ids[0], [])) < 2:
            c.create_text(w / 2, h / 2, text="Waiting for live readings", fill=MUTED)
            return
        history = self.history[ids[0]]
        end = history[-1][0]
        history = [p for p in history if end - p[0] <= 60]
        span = max(10, end - history[0][0])
        pts = []
        for t, p in history:
            pts.extend(
                (
                    38 + (t - (end - span)) / span * (w - 52),
                    h - 18 - p / 1023 * (h - 34),
                )
            )
        if len(pts) >= 4:
            c.create_line(*pts, fill=BLUE, width=2)

    def mark_offline(self, message):
        self.pending_action = None
        self.pending_release = None
        for sid, r in self.rows.items():
            r.update(ok=False, error=message)
            self.history[sid] = []
            self.render(sid)
        self.draw_graph()

    def poll(self):
        try:
            while True:
                kind, data, error = self.events.get_nowait()
                if kind == "progress":
                    if not self.pending_release:
                        self.status.set(data)
                    continue
                self.busy = False
                self.busy_kind = None
                if kind == "link_lost":
                    self.connected = False
                    self.last_reconnect = time.monotonic()
                    self.mark_offline("USB connection lost; waiting for the adapter.")
                    self.status.set(
                        "USB disconnected. Pending commands were discarded. "
                        + (
                            "Movement may have partially completed; inspect the servos before moving again."
                            if data == "move"
                            else ""
                        )
                    )
                elif error:
                    self.status.set(error)
                    if kind in ("connect", "reconnect"):
                        self.connected = False
                        self.last_reconnect = time.monotonic()
                    if kind == "move":
                        self.mark_offline(
                            "Move did not complete normally; read position before retrying."
                        )
                elif kind in ("connect", "reconnect"):
                    self.connected = True
                    self.status.set(
                        "USB connected. Checking servo power and readings; no movement sent."
                    )
                    if not self.closing:
                        if self.rows:
                            self.read_now()
                        else:
                            self.scan()
                elif kind == "disconnect":
                    self.connected = False
                    self.mark_offline("Disconnected")
                    self.status.set(
                        "Disconnected. Prepared targets kept; torque unchanged."
                    )
                elif kind == "scan":
                    found, errors, cancelled = data
                    if not cancelled:
                        for i in self.scan_ids.intersection(self.rows) - set(found):
                            self.rows[i].update(
                                ok=False, error="No reading. Check servo power."
                            )
                            self.history[i] = []
                            self.render(i)
                    self.update_rows(found)
                    self.update_rows(
                        {i: {"error": e} for i, e in errors.items() if i in self.rows}
                    )
                    self.status.set(
                        f'{"Scan cancelled" if cancelled else "Scan complete"} · {len(found)} ready · {len(errors)} errors. '
                        + (
                            "Check servo power and wiring; duplicate IDs can also corrupt replies."
                            if errors
                            else (
                                "No replies. Restore power and try again."
                                if not found
                                else "Select rows, prepare targets, then Move selected."
                            )
                        )
                    )
                elif kind == "read":
                    self.update_rows(data)
                    if data and not any("error" not in d for d in data.values()):
                        # Discard actions queued during this read if power was lost.
                        if self.pending_action and self.pending_action[0] == "move":
                            self.pending_action = None
                else:
                    self.status.set(data)
                    self.last_poll = 0
                self.controls()
        except queue.Empty:
            pass
        if self.closing and not self.busy:
            self.bus.close()
            self.root.destroy()
            return
        if not self.busy and not self.closing:
            if self.pending_release and self.connected:
                ids = self.pending_release
                self.pending_release = None
                self.submit("release", lambda: self.bus.release(ids))
            elif self.pending_action:
                args = self.pending_action
                self.pending_action = None
                self.submit(*args)
            elif (
                self.want_connection
                and not self.connected
                and time.monotonic() - self.last_reconnect > 3
            ):
                self.last_reconnect = time.monotonic()
                self.reconnect()
            elif self.connected and self.live.get():
                if self.rows and time.monotonic() - self.last_poll > (
                    1 if any(r.get("ok") for r in self.rows.values()) else 2
                ):
                    self.last_poll = time.monotonic()
                    ids = list(self.rows)
                    self.submit("read", lambda: self.snapshots(ids), quiet=True)
                elif not self.rows and time.monotonic() - self.last_discovery > 8:
                    self.scan()
        self.controls()
        self.root.after(100, self.poll)

    def close(self):
        self.closing = True
        self.want_connection = False
        self.pending_action = None
        self.pending_release = None
        self.cancel.set()
        self.live.set(False)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
