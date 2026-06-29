import base64
import io
import json
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import fitz  # PyMuPDF
from PIL import Image, ImageTk

# Import the backend automation module
import automate_login

# Colors
BG_COLOR = "#1E1E1E"  # Main dark background
CARD_BG_COLOR = "#121212"  # Cards/Sub-panels darker background
TEXT_COLOR = "#E0E0E0"  # Off-white primary text
TEXT_LIGHT_COLOR = "#A0A0A0"  # Muted subtext
ACCENT_COLOR = "#2563EB"  # Electric Blue primary
ACCENT_HOVER = "#3B82F6"  # Light blue button hover
SUCCESS_COLOR = "#10B981"  # Emerald green for matches/approvals
WARNING_COLOR = "#F59E0B"  # Amber warning color for holds
ERROR_COLOR = "#EF4444"  # Red for mismatches/errors
BORDER_COLOR = "#2E2E2E"  # Subtle border/separator lines


class StdoutRedirector:
    """Redirects stdout/stderr streams thread-safely via a Queue to a Tkinter Text widget."""

    def __init__(self, log_queue, original_stream, default_tag=None):
        self.log_queue = log_queue
        self.original_stream = original_stream
        self.default_tag = default_tag

    def write(self, string):
        try:
            self.original_stream.write(string)
        except Exception:
            pass
        self.log_queue.put((string, self.default_tag))

    def flush(self):
        try:
            self.original_stream.flush()
        except Exception:
            pass


class AppUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mahindra KYC Process Automation Dashboard")
        self.geometry("1400x900")
        self.configure(bg=BG_COLOR)

        # Main state variables
        self.automation_thread = None
        self.input_queue = queue.Queue()
        self.input_event = threading.Event()
        self.input_prompt = ""
        self.input_type = ""
        self.input_options = []
        self.input_result = None

        self.row_queue = queue.Queue()
        self.processed_claims = []

        # Selected claim details
        self.selected_claim = None
        self.current_pdf_path = None
        self.current_pdf_doc = None
        self.current_pdf_page = 0
        self.current_zoom = 1.2
        self.canvas_photo = None

        # Configure overall styles
        self.setup_styles()

        # Create UI Panels
        self.create_layout()

        # Main thread log queue
        self.log_queue = queue.Queue()

        # Redirect standard outputs and logs
        sys.stdout = StdoutRedirector(self.log_queue, sys.stdout)
        sys.stderr = StdoutRedirector(self.log_queue, sys.stderr, "error")

        # Hook up python logger
        class TextHandler(logging.Handler):
            def __init__(self, app_instance):
                super().__init__()
                self.app = app_instance

            def emit(self, record):
                msg = self.format(record)
                self.app.log_queue.put((msg + "\n", None))

        logger = logging.getLogger()
        logger.addHandler(TextHandler(self))

        # Load any existing history from local JSON
        self.load_history_from_file()

        # Create FAB Toplevel Window (initially withdrawn/hidden)
        self.create_fab_window()

        # Start main thread polling loop
        self.poll_queues()

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Configure generic colors
        style.configure(
            ".",
            background=BG_COLOR,
            foreground=TEXT_COLOR,
            fieldbackground=CARD_BG_COLOR,
        )

        # Frame
        style.configure("TFrame", background=BG_COLOR)
        style.configure(
            "Card.TFrame", background=CARD_BG_COLOR, borderwidth=1, relief="solid"
        )

        # Notebook (tabs)
        style.configure("TNotebook", background=BG_COLOR, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=CARD_BG_COLOR,
            foreground=TEXT_LIGHT_COLOR,
            padding=[10, 5],
            font=("Segoe UI", 9),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", BG_COLOR)],
            foreground=[("selected", TEXT_COLOR)],
        )

        # Treeview (Modern list style)
        style.configure(
            "Treeview",
            background=CARD_BG_COLOR,
            foreground=TEXT_COLOR,
            fieldbackground=CARD_BG_COLOR,
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", ACCENT_COLOR)],
            foreground=[("selected", "#FFFFFF")],
        )
        style.configure(
            "Treeview.Heading",
            background=BG_COLOR,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )

        # Combobox
        style.configure(
            "TCombobox",
            fieldbackground="#2A2A2A",
            background=BG_COLOR,
            foreground=TEXT_COLOR,
        )

        # Scrollbar
        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background="#2A2A2A",
            troughcolor=CARD_BG_COLOR,
            borderwidth=0,
            arrowsize=10,
        )

    def create_layout(self):
        # 1. Header Area with Toggle Button
        self.header_frame = tk.Frame(self, bg=CARD_BG_COLOR, height=60)
        self.header_frame.pack(fill="x", side="top")
        self.header_frame.pack_propagate(False)

        title_lbl = tk.Label(
            self.header_frame,
            text="MAHINDRA KYC PROCESS AUTOMATION",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 14, "bold"),
        )
        title_lbl.pack(side="left", padx=20, pady=15)

        self.zone_lbl = tk.Label(
            self.header_frame,
            text="Active Zone: COMMON",
            bg=CARD_BG_COLOR,
            fg="#F59E0B",
            font=("Segoe UI", 11, "bold"),
        )
        self.zone_lbl.pack(side="left", padx=(10, 20), pady=15)

        # Minimize to FAB action button
        self.fab_toggle_btn = tk.Button(
            self.header_frame,
            text="Minimize to FAB",
            bg="#2D3748",
            fg=TEXT_COLOR,
            activebackground="#4A5568",
            activeforeground=TEXT_COLOR,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=12,
            pady=6,
            command=self.minimize_to_fab,
        )
        self.fab_toggle_btn.pack(side="right", padx=20, pady=12)

        # 2. Main split panes
        self.main_pane = tk.PanedWindow(
            self, orient="horizontal", bg=BG_COLOR, bd=0, sashwidth=6, sashrelief="flat"
        )
        self.main_pane.pack(fill="both", expand=True, padx=10, pady=10)

        # Left Panel (Controls & Console log)
        self.left_panel = tk.Frame(self.main_pane, bg=BG_COLOR, width=450)
        self.left_panel.pack_propagate(False)
        self.main_pane.add(self.left_panel)

        # Start panel controls card
        self.controls_card = tk.LabelFrame(
            self.left_panel,
            text="Automation Parameters",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=15,
            relief="solid",
            bd=1,
        )
        self.controls_card.pack(fill="x", side="top", pady=(0, 10))

        # Login Choice Option
        tk.Label(
            self.controls_card,
            text="Login Choice Mode:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=0, column=0, sticky="w", pady=6)
        self.login_mode_var = tk.StringVar(value="Already Login")
        self.login_mode_combo = ttk.Combobox(
            self.controls_card,
            textvariable=self.login_mode_var,
            values=["Already Login", "New Login"],
            state="readonly",
            width=18,
        )
        self.login_mode_combo.grid(row=0, column=1, sticky="w", padx=10, pady=6)

        # Claim Selection Choice
        tk.Label(
            self.controls_card,
            text="Claim Type Category:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, sticky="w", pady=6)
        self.claim_choice_var = tk.StringVar(value="Loyalty Claims")
        self.claim_choice_combo = ttk.Combobox(
            self.controls_card,
            textvariable=self.claim_choice_var,
            values=["Loyalty Claims", "Exchange Claim"],
            state="readonly",
            width=18,
        )
        self.claim_choice_combo.grid(row=1, column=1, sticky="w", padx=10, pady=6)

        # Rows Limit Bounds Option
        tk.Label(
            self.controls_card,
            text="Row Bounds Limit:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=2, column=0, sticky="w", pady=6)
        self.row_limit_var = tk.StringVar(value="a")
        self.row_limit_combo = ttk.Combobox(
            self.controls_card,
            textvariable=self.row_limit_var,
            values=["a", "1", "2", "3", "4", "5", "1,3,5", "2-4"],
            state="normal",
            width=18,
        )
        self.row_limit_combo.grid(row=2, column=1, sticky="w", padx=10, pady=6)

        # Helper text for custom rows
        self.row_helper_lbl = tk.Label(
            self.controls_card,
            text="* Type custom rows e.g. 1,3,5 or 2-4",
            bg=CARD_BG_COLOR,
            fg=TEXT_LIGHT_COLOR,
            font=("Segoe UI", 8, "italic"),
        )
        self.row_helper_lbl.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 4))

        # Action Buttons
        self.start_btn = tk.Button(
            self.controls_card,
            text="RUN AUTOMATION PROCESS",
            bg=ACCENT_COLOR,
            fg="#FFFFFF",
            activebackground=ACCENT_HOVER,
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            pady=8,
            bd=0,
            command=self.start_automation,
        )
        self.start_btn.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # Real-time styled terminal console logs log widget
        self.log_card = tk.LabelFrame(
            self.left_panel,
            text="Real-time Execution Console",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 10, "bold"),
            relief="solid",
            bd=1,
        )
        self.log_card.pack(fill="both", expand=True)

        self.log_console = tk.Text(
            self.log_card,
            bg="#0D0D0D",
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            wrap="word",
            font=("Consolas", 9),
            bd=0,
        )
        self.log_console.pack(fill="both", expand=True, side="left", padx=5, pady=5)

        # Console tags styling
        self.log_console.tag_config("error", foreground=ERROR_COLOR)
        self.log_console.tag_config("success", foreground=SUCCESS_COLOR)
        self.log_console.tag_config("warning", foreground=WARNING_COLOR)
        self.log_console.configure(state="disabled")

        log_scroll = ttk.Scrollbar(self.log_card, command=self.log_console.yview)
        log_scroll.pack(fill="y", side="right")
        self.log_console.configure(yscrollcommand=log_scroll.set)

        # Right Panel (Splits into Processed Treeview list and main Comparison viewer)
        self.right_panel = tk.Frame(self.main_pane, bg=BG_COLOR)
        self.main_pane.add(self.right_panel)

        self.right_split = tk.PanedWindow(
            self.right_panel,
            orient="horizontal",
            bg=BG_COLOR,
            bd=0,
            sashwidth=6,
            sashrelief="flat",
        )
        self.right_split.pack(fill="both", expand=True)

        # Row History Treeview Panel (Left side)
        self.history_frame = tk.LabelFrame(
            self.right_split,
            text="Processed Rows History",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 10, "bold"),
            relief="solid",
            bd=1,
            width=280,
        )
        self.history_frame.pack_propagate(False)
        self.right_split.add(self.history_frame)

        self.history_tree = ttk.Treeview(
            self.history_frame,
            columns=("Row", "Customer", "Status"),
            show="headings",
            selectmode="browse",
        )
        self.history_tree.heading("Row", text="Idx")
        self.history_tree.heading("Customer", text="Customer Name")
        self.history_tree.heading("Status", text="Verification Status")

        self.history_tree.column("Row", width=50, anchor="center")
        self.history_tree.column("Customer", width=140, anchor="w")
        self.history_tree.column("Status", width=80, anchor="center")

        self.history_tree.tag_configure(
            "approved", foreground=SUCCESS_COLOR, font=("Segoe UI", 9, "bold")
        )
        self.history_tree.tag_configure(
            "hold", foreground=WARNING_COLOR, font=("Segoe UI", 9, "bold")
        )
        self.history_tree.bind("<<TreeviewSelect>>", self.on_history_select)

        self.history_tree.pack(fill="both", expand=True, side="left", padx=5, pady=5)

        hist_scroll = ttk.Scrollbar(self.history_frame, command=self.history_tree.yview)
        hist_scroll.pack(fill="y", side="right")
        self.history_tree.configure(yscrollcommand=hist_scroll.set)

        # 3. Main Details card split viewer
        self.viewer_frame = tk.Frame(self.right_split, bg=BG_COLOR)
        self.right_split.add(self.viewer_frame)

        # Placeholder welcome label
        self.placeholder_lbl = tk.Label(
            self.viewer_frame,
            text="Select a row from history list\nto inspect verification details & PDF document comparison.",
            bg=BG_COLOR,
            fg=TEXT_LIGHT_COLOR,
            font=("Segoe UI", 12, "italic"),
        )
        self.placeholder_lbl.pack(fill="both", expand=True)

        # Details view pane container (initially hidden)
        self.details_container = tk.Frame(self.viewer_frame, bg=BG_COLOR)

        # Split: Details text metrics (Left) vs. Interactive PDF view Canvas (Right)
        self.comparison_split = tk.PanedWindow(
            self.details_container,
            orient="horizontal",
            bg=BG_COLOR,
            bd=0,
            sashwidth=6,
            sashrelief="flat",
        )
        self.comparison_split.pack(fill="both", expand=True)

        # Left metrics columns
        self.metrics_pane = tk.Frame(self.comparison_split, bg=BG_COLOR, width=450)
        self.metrics_pane.pack_propagate(False)
        self.comparison_split.add(self.metrics_pane)

        # Grid list inside metrics pane
        self.details_notebook = ttk.Notebook(self.metrics_pane)
        self.details_notebook.pack(fill="both", expand=True)

        # Tab 1: Dashboard Data
        self.tab_dash = tk.Frame(self.details_notebook, bg=CARD_BG_COLOR)
        self.details_notebook.add(self.tab_dash, text="Dashboard Info")

        self.dash_tree = ttk.Treeview(
            self.tab_dash, columns=("Field", "Value"), show="headings"
        )
        self.dash_tree.heading("Field", text="Dashboard Field Key")
        self.dash_tree.heading("Value", text="Value")
        self.dash_tree.column("Field", width=160, anchor="w")
        self.dash_tree.column("Value", width=260, anchor="w")
        self.dash_tree.pack(fill="both", expand=True, side="left", padx=5, pady=5)

        dash_scroll = ttk.Scrollbar(self.tab_dash, command=self.dash_tree.yview)
        dash_scroll.pack(fill="y", side="right")
        self.dash_tree.configure(yscrollcommand=dash_scroll.set)

        # Tab 2: Document Extracted Data
        self.tab_doc = tk.Frame(self.details_notebook, bg=CARD_BG_COLOR)
        self.details_notebook.add(self.tab_doc, text="Document Data (GPT)")

        self.doc_tree = ttk.Treeview(
            self.tab_doc, columns=("Field", "Value"), show="headings"
        )
        self.doc_tree.heading("Field", text="Extracted Field Key")
        self.doc_tree.heading("Value", text="Value")
        self.doc_tree.column("Field", width=160, anchor="w")
        self.doc_tree.column("Value", width=260, anchor="w")
        self.doc_tree.pack(fill="both", expand=True, side="left", padx=5, pady=5)

        doc_scroll = ttk.Scrollbar(self.tab_doc, command=self.doc_tree.yview)
        doc_scroll.pack(fill="y", side="right")
        self.doc_tree.configure(yscrollcommand=doc_scroll.set)

        # Tab 3: Verification Checks / Status
        self.tab_checks = tk.Frame(self.details_notebook, bg=CARD_BG_COLOR)
        self.details_notebook.add(self.tab_checks, text="Validation Checks")

        self.checks_text = tk.Text(
            self.tab_checks,
            bg="#0F0F0F",
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
            wrap="word",
            padx=10,
            pady=10,
            bd=0,
        )
        self.checks_text.pack(fill="both", expand=True, side="left", padx=5, pady=5)
        self.checks_text.tag_config("match", foreground=SUCCESS_COLOR)
        self.checks_text.tag_config("mismatch", foreground=ERROR_COLOR)
        self.checks_text.tag_config(
            "title", foreground="#60A5FA", font=("Segoe UI", 10, "bold")
        )
        self.checks_text.tag_config("issue", foreground=WARNING_COLOR)
        self.checks_text.configure(state="disabled")

        checks_scroll = ttk.Scrollbar(self.tab_checks, command=self.checks_text.yview)
        checks_scroll.pack(fill="y", side="right")
        self.checks_text.configure(yscrollcommand=checks_scroll.set)

        # Tab 4: East Welcome Bonus Disclaimer
        self.tab_east_welcome = tk.Frame(self.details_notebook, bg=CARD_BG_COLOR)
        self.details_notebook.add(self.tab_east_welcome, text="East Welcome Disclaimer")
        
        self.east_top_frame = tk.Frame(self.tab_east_welcome, bg=CARD_BG_COLOR)
        self.east_top_frame.pack(fill="x", padx=5, pady=5)
        
        self.east_analyze_btn = tk.Button(self.east_top_frame, text="Analyze Disclaimer (OpenAI)", bg="#667eea", fg="white", font=("Segoe UI", 10, "bold"), command=self.run_east_disclaimer_analysis)
        self.east_analyze_btn.pack(side="left")
        
        self.east_status_lbl = tk.Label(self.east_top_frame, text="", bg=CARD_BG_COLOR, fg=TEXT_COLOR)
        self.east_status_lbl.pack(side="left", padx=10)

        self.east_canvas = tk.Canvas(self.tab_east_welcome, bg=CARD_BG_COLOR, highlightthickness=0)
        self.east_scroll = ttk.Scrollbar(self.tab_east_welcome, orient="vertical", command=self.east_canvas.yview)
        self.east_scroll.pack(side="right", fill="y")
        self.east_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.east_canvas.configure(yscrollcommand=self.east_scroll.set)
        
        self.east_frame = tk.Frame(self.east_canvas, bg=CARD_BG_COLOR)
        self.east_canvas.create_window((0, 0), window=self.east_frame, anchor="nw")
        
        def on_east_frame_configure(event):
            self.east_canvas.configure(scrollregion=self.east_canvas.bbox("all"))
            
        self.east_frame.bind("<Configure>", on_east_frame_configure)


        # Right Interactive Canvas Frame for PDF display
        self.pdf_frame = tk.Frame(self.comparison_split, bg=BG_COLOR)
        self.comparison_split.add(self.pdf_frame)

        # Toolbars for PDF: Selector dropdown, Zoom +/-, Prev/Next Page
        self.pdf_toolbar = tk.Frame(self.pdf_frame, bg=CARD_BG_COLOR, height=45)
        self.pdf_toolbar.pack(fill="x", side="top")
        self.pdf_toolbar.pack_propagate(False)

        # Dropdown selection of PDF files
        tk.Label(
            self.pdf_toolbar,
            text="Document:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=10)
        self.doc_selector_var = tk.StringVar()
        self.doc_selector = ttk.Combobox(
            self.pdf_toolbar,
            textvariable=self.doc_selector_var,
            state="readonly",
            width=30,
        )
        self.doc_selector.pack(side="left", padx=5)
        self.doc_selector.bind("<<ComboboxSelected>>", self.on_doc_combo_select)

        # Prev / Next
        self.prev_btn = tk.Button(
            self.pdf_toolbar,
            text=" ◀ ",
            bg="#2D3748",
            fg=TEXT_COLOR,
            activebackground="#4A5568",
            relief="flat",
            font=("Segoe UI", 9),
            bd=0,
            command=self.prev_pdf_page,
        )
        self.prev_btn.pack(side="left", padx=(15, 5))

        self.page_label = tk.Label(
            self.pdf_toolbar,
            text="Page 0 of 0",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        )
        self.page_label.pack(side="left", padx=5)

        self.next_btn = tk.Button(
            self.pdf_toolbar,
            text=" ▶ ",
            bg="#2D3748",
            fg=TEXT_COLOR,
            activebackground="#4A5568",
            relief="flat",
            font=("Segoe UI", 9),
            bd=0,
            command=self.next_pdf_page,
        )
        self.next_btn.pack(side="left", padx=5)

        # Zoom Controls
        self.zoom_out_btn = tk.Button(
            self.pdf_toolbar,
            text=" Zoom - ",
            bg="#2D3748",
            fg=TEXT_COLOR,
            activebackground="#4A5568",
            relief="flat",
            font=("Segoe UI", 9),
            bd=0,
            command=self.zoom_out_pdf,
        )
        self.zoom_out_btn.pack(side="right", padx=5, pady=8)

        self.zoom_lbl = tk.Label(
            self.pdf_toolbar,
            text="120%",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        )
        self.zoom_lbl.pack(side="right", padx=5)

        self.zoom_in_btn = tk.Button(
            self.pdf_toolbar,
            text=" Zoom + ",
            bg="#2D3748",
            fg=TEXT_COLOR,
            activebackground="#4A5568",
            relief="flat",
            font=("Segoe UI", 9),
            bd=0,
            command=self.zoom_in_pdf,
        )
        self.zoom_in_btn.pack(side="right", padx=(10, 5), pady=8)

        # Interactive PDF Canvas
        self.canvas_container = tk.Frame(self.pdf_frame, bg="#262626")
        self.canvas_container.pack(fill="both", expand=True)

        self.pdf_canvas = tk.Canvas(
            self.canvas_container, bg="#262626", highlightthickness=0
        )
        self.pdf_canvas.pack(fill="both", expand=True, side="left")

        pdf_vscroll = ttk.Scrollbar(
            self.canvas_container, orient="vertical", command=self.pdf_canvas.yview
        )
        pdf_vscroll.pack(fill="y", side="right")
        pdf_hscroll = ttk.Scrollbar(
            self.pdf_frame, orient="horizontal", command=self.pdf_canvas.xview
        )
        pdf_hscroll.pack(fill="x", side="bottom")

        self.pdf_canvas.configure(
            yscrollcommand=pdf_vscroll.set, xscrollcommand=pdf_hscroll.set
        )

        # Pan-by-drag mouse bindings
        self.pdf_canvas.bind("<Button-1>", self.start_pan)
        self.pdf_canvas.bind("<B1-Motion>", self.drag_pan)
        # Mousewheel scroll binding
        self.pdf_canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)

        # ═══════════════════════════════════════════════════════════
        # VISUAL CONFIRMATIONS PANEL (NEW!)
        # ═══════════════════════════════════════════════════════════
        self.visual_panel = tk.LabelFrame(
            self.right_split,
            text="🔍 Visual Confirmations",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 10, "bold"),
            relief="solid",
            bd=1,
            width=380,
        )
        self.visual_panel.pack_propagate(False)
        self.right_split.add(self.visual_panel)

        # Scrollable canvas for visual items
        visual_scroll_container = tk.Frame(self.visual_panel, bg=CARD_BG_COLOR)
        visual_scroll_container.pack(fill="both", expand=True, padx=5, pady=5)

        self.visual_canvas = tk.Canvas(
            visual_scroll_container, bg=BG_COLOR, highlightthickness=0
        )
        visual_scrollbar = ttk.Scrollbar(
            visual_scroll_container,
            orient=tk.VERTICAL,
            command=self.visual_canvas.yview,
        )

        self.visual_frame = tk.Frame(self.visual_canvas, bg=BG_COLOR)

        self.visual_frame.bind(
            "<Configure>",
            lambda e: self.visual_canvas.configure(
                scrollregion=self.visual_canvas.bbox("all")
            ),
        )

        self.visual_canvas.create_window((0, 0), window=self.visual_frame, anchor="nw")
        self.visual_canvas.configure(yscrollcommand=visual_scrollbar.set)

        self.visual_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        visual_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling for visual panel
        def on_visual_mousewheel(event):
            self.visual_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.visual_canvas.bind("<MouseWheel>", on_visual_mousewheel)

        # Placeholder
        self.visual_placeholder = tk.Label(
            self.visual_frame,
            text="👁️ Visual extractions\nwill appear here",
            font=("Segoe UI", 10),
            fg=TEXT_LIGHT_COLOR,
            bg=BG_COLOR,
            justify=tk.CENTER,
        )
        self.visual_placeholder.pack(pady=60)

        # Store PhotoImage references
        self.extraction_images = []

    # Mouse drag-to-pan functions
    def start_pan(self, event):
        self.pdf_canvas.scan_mark(event.x, event.y)

    def drag_pan(self, event):
        self.pdf_canvas.scan_dragto(event.x, event.y, gain=1)

    def on_mouse_wheel(self, event):
        # Vertical scroll canvas
        try:
            self.pdf_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    # Redirect logging handler callback
    def append_log_message(self, msg):
        self.log_console.configure(state="normal")
        tag = None
        msg_upper = msg.upper()
        if (
            "MISMATCH" in msg_upper
            or "FAILED" in msg_upper
            or "ERROR" in msg_upper
            or "CRITICAL" in msg_upper
        ):
            tag = "error"
        elif (
            "MATCH" in msg_upper
            or "APPROVED" in msg_upper
            or "FINE" in msg_upper
            or "✔" in msg
        ):
            tag = "success"
        elif "WARNING" in msg_upper or "HOLD" in msg_upper or "⚠" in msg:
            tag = "warning"

        if tag:
            self.log_console.insert("end", msg, tag)
        else:
            self.log_console.insert("end", msg)
        self.log_console.configure(state="disabled")
        self.log_console.see("end")

    def poll_queues(self):
        # Update active zone display from backend
        try:
            zone = getattr(automate_login, "CURRENT_ZONE", "COMMON")
            self.zone_lbl.configure(text=f"Active Zone: {zone}")
            if zone == "EAST":
                self.zone_lbl.configure(fg="#10B981")  # Green color for East
            elif zone in ["SOUTH", "WEST", "NORTH"]:
                self.zone_lbl.configure(fg="#60A5FA")  # Blue for other active zones
            else:
                self.zone_lbl.configure(fg="#F59E0B")  # Amber/orange for common/unknown
        except Exception:
            pass

        # 1. Check if there is an input request
        if not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
                self.handle_input_request()
            except queue.Empty:
                pass
            except Exception as e:
                logging.error(f"Error handling input request: {e}")

        # 2. Check if there are completed rows
        while not self.row_queue.empty():
            try:
                row_result = self.row_queue.get_nowait()
                self.handle_row_complete(row_result)
            except queue.Empty:
                break
            except Exception as e:
                logging.error(f"Error handling completed row: {e}")

        # 3. Check for log messages
        log_msgs = []
        while not self.log_queue.empty():
            try:
                log_msgs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
            if len(log_msgs) > 100:  # Batch limit
                break

        if log_msgs:
            try:
                self.log_console.configure(state="normal")
                for msg, tag in log_msgs:
                    if not msg:
                        continue
                    # Color tag check if not explicitly set
                    if tag is None:
                        msg_upper = msg.upper()
                        if (
                            "MISMATCH" in msg_upper
                            or "FAILED" in msg_upper
                            or "ERROR" in msg_upper
                            or "CRITICAL" in msg_upper
                        ):
                            tag = "error"
                        elif (
                            "MATCH" in msg_upper
                            or "APPROVED" in msg_upper
                            or "FINE" in msg_upper
                            or "✔" in msg
                        ):
                            tag = "success"
                        elif (
                            "WARNING" in msg_upper or "HOLD" in msg_upper or "⚠" in msg
                        ):
                            tag = "warning"

                    if tag:
                        self.log_console.insert("end", msg, tag)
                    else:
                        self.log_console.insert("end", msg)
                self.log_console.configure(state="disabled")
                self.log_console.see("end")
            except Exception:
                pass

        # Poll again in 100ms
        try:
            self.after(100, self.poll_queues)
        except Exception:
            pass

    # Start Playwright automation thread
    def start_automation(self):
        if self.automation_thread and self.automation_thread.is_alive():
            messagebox.showwarning("Running", "Automation is already in progress.")
            return

        # Disable controls during run
        self.start_btn.configure(
            state="disabled", text="RUNNING PROCESS...", bg="#4B5563"
        )
        self.login_mode_combo.configure(state="disabled")
        self.claim_choice_combo.configure(state="disabled")
        self.row_limit_combo.configure(state="disabled")

        # Clean console log
        self.log_console.configure(state="normal")
        self.log_console.delete("1.0", "end")
        self.log_console.configure(state="disabled")

        # Clear dynamic UI documents variables
        automate_login.UI_RUNNING = True
        automate_login.UI_INPUT_CALLBACK = self.ui_input_callback_bridge
        automate_login.UI_ROW_COMPLETE_CALLBACK = self.ui_row_complete_callback_bridge

        # Launch worker Thread
        self.automation_thread = threading.Thread(
            target=self.run_automation_task, daemon=True
        )
        self.automation_thread.start()

    def run_automation_task(self):
        login_choice = self.login_mode_var.get() == "Already Login"
        claim_choice = "1" if self.claim_choice_var.get() == "Loyalty Claims" else "2"
        row_limit = self.row_limit_var.get()

        try:
            automate_login.main(
                use_existing_login=login_choice,
                target_claim_choice=claim_choice,
                row_limit=row_limit,
            )
            logging.info("Batch automation processing run finished successfully.")
        except Exception as e:
            logging.exception(f"Fatal error occurred in automation worker: {e}")
        finally:
            automate_login.UI_RUNNING = False
            self.after(0, self.reset_ui_controls)

    def reset_ui_controls(self):
        self.start_btn.configure(
            state="normal", text="RUN AUTOMATION PROCESS", bg=ACCENT_COLOR
        )
        self.login_mode_combo.configure(state="readonly")
        self.claim_choice_combo.configure(state="readonly")
        self.row_limit_combo.configure(state="normal")

    # Bridge between threads: automation thread requests UI inputs
    def ui_input_callback_bridge(self, prompt, prompt_type="text", options=None):
        self.input_prompt = prompt
        self.input_type = prompt_type
        self.input_options = options or []
        self.input_result = None
        self.input_event.clear()

        # Put token in queue to trigger polling
        self.input_queue.put(True)

        # Block automation thread wait for event trigger
        self.input_event.wait()
        return self.input_result

    # Modal popup handler on GUI thread
    def handle_input_request(self, event=None):
        # Build modal dialog on main UI thread
        dialog = tk.Toplevel(self)
        dialog.title("Verification Input Prompt Required")
        dialog.configure(bg=CARD_BG_COLOR)
        dialog.transient(self)
        dialog.grab_set()

        dialog.geometry("480x280")
        x = self.winfo_x() + (self.winfo_width() // 2) - 240
        y = self.winfo_y() + (self.winfo_height() // 2) - 140
        dialog.geometry(f"+{x}+{y}")

        lbl = tk.Label(
            dialog,
            text=self.input_prompt,
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 10, "bold"),
            wraplength=420,
            justify="center",
        )
        lbl.pack(pady=20, padx=20)

        var_res = tk.StringVar()
        entry = None
        combo = None

        # Layout depends on type of expected inputs
        if self.input_type == "password":
            entry = tk.Entry(
                dialog,
                textvariable=var_res,
                show="*",
                bg="#2A2A2A",
                fg=TEXT_COLOR,
                insertbackground=TEXT_COLOR,
                font=("Segoe UI", 12),
                relief="flat",
                bd=2,
            )
            entry.pack(pady=10, padx=40, fill="x")
            entry.focus_set()
        elif self.input_type == "otp":
            entry = tk.Entry(
                dialog,
                textvariable=var_res,
                bg="#2A2A2A",
                fg=TEXT_COLOR,
                insertbackground=TEXT_COLOR,
                font=("Segoe UI", 16, "bold"),
                relief="flat",
                bd=2,
                justify="center",
            )
            entry.pack(pady=10, padx=120, fill="x")
            entry.focus_set()
        elif self.input_type == "dropdown" and self.input_options:
            combo = ttk.Combobox(
                dialog,
                values=self.input_options,
                state="readonly",
                font=("Segoe UI", 10),
            )
            combo.pack(pady=10, padx=40, fill="x")
            combo.set(self.input_options[0])
            combo.focus_set()
        elif self.input_type == "choice" and self.input_options:
            btn_frame = tk.Frame(dialog, bg=CARD_BG_COLOR)
            btn_frame.pack(pady=20)
            for opt in self.input_options:
                btn = tk.Button(
                    btn_frame,
                    text=opt,
                    width=12,
                    bg=ACCENT_COLOR,
                    fg="#FFFFFF",
                    activebackground=ACCENT_HOVER,
                    relief="flat",
                    font=("Segoe UI", 9, "bold"),
                    bd=0,
                    command=lambda o=opt: [var_res.set(o), dialog.destroy()],
                )
                btn.pack(side="left", padx=10)
        else:
            entry = tk.Entry(
                dialog,
                textvariable=var_res,
                bg="#2A2A2A",
                fg=TEXT_COLOR,
                insertbackground=TEXT_COLOR,
                font=("Segoe UI", 10),
                relief="flat",
                bd=2,
            )
            entry.pack(pady=10, padx=40, fill="x")
            entry.focus_set()

        def on_submit(ev=None):
            if self.input_type == "dropdown" and combo:
                var_res.set(combo.get())
            elif self.input_type == "choice" and self.input_options:
                return
            dialog.destroy()

        if entry:
            entry.bind("<Return>", on_submit)
        if combo:
            combo.bind("<Return>", on_submit)

        if self.input_type != "choice" or not self.input_options:
            submit_btn = tk.Button(
                dialog,
                text="Submit Action",
                bg=ACCENT_COLOR,
                fg="#FFFFFF",
                activebackground=ACCENT_HOVER,
                relief="flat",
                font=("Segoe UI", 10, "bold"),
                width=15,
                bd=0,
                command=on_submit,
            )
            submit_btn.pack(pady=20)

        # Block GUI execution until window closes
        self.wait_window(dialog)

        # Save results and trigger threading event release lock
        self.input_result = var_res.get()
        self.input_event.set()

    # Bridge between threads: row completion callback
    def ui_row_complete_callback_bridge(self, row_result):
        self.row_queue.put(row_result)

    # Row completed handler on GUI thread
    def handle_row_complete(self, row_result):
        self.processed_claims.append(row_result)

        # Insert into visual list tree
        status_tag = "approved" if row_result["status"] == "APPROVED" else "hold"
        node_id = self.history_tree.insert(
            "",
            "end",
            values=(
                f"Row {row_result['row_idx'] + 1}",
                row_result["customer_name"],
                row_result["status"],
            ),
            tags=(status_tag,),
        )
        # Automatically highlight and select the newly completed row
        self.history_tree.selection_set(node_id)
        self.history_tree.see(node_id)

    # Load history panel when user selects list elements
    def on_history_select(self, event):
        selected_items = self.history_tree.selection()
        if not selected_items:
            return

        item = selected_items[0]
        # Match by row index
        row_text = self.history_tree.item(item, "values")[0]
        try:
            row_idx = int(row_text.split()[-1]) - 1
        except Exception:
            return

        # Find matching item in processed list
        claim = None
        for c in reversed(self.processed_claims):
            if c.get("row_idx") == row_idx:
                claim = c
                break

        if not claim:
            return

        self.load_claim_to_viewer(claim)

    def load_claim_to_viewer(self, claim):
        self.selected_claim = claim

        # Show details panel, hide placeholder
        self.placeholder_lbl.pack_forget()
        self.details_container.pack(fill="both", expand=True)

        # 1. Populate Dashboard details Tree
        for item in self.dash_tree.get_children():
            self.dash_tree.delete(item)

        c_details = claim.get("claim_details") or {}
        v_details = claim.get("old_vehicle_details") or {}

        for k, v in c_details.items():
            self.dash_tree.insert("", "end", values=(k, v))
        for k, v in v_details.items():
            self.dash_tree.insert("", "end", values=(f"[Old Veh] {k}", v))

        # 2. Populate PDF selector toolbar values
        documents = claim.get("documents") or []
        doc_names = [doc.get("file_name") for doc in documents]

        self.doc_selector.configure(values=doc_names)
        if doc_names:
            self.doc_selector.set(doc_names[0])
            self.load_selected_pdf_document(documents[0])
        else:
            self.doc_selector.set("No Documents Found")
            self.pdf_canvas.delete("all")
            self.page_label.config(text="Page 0 of 0")

            # Clear doc tree
            for item in self.doc_tree.get_children():
                self.doc_tree.delete(item)
            # Clear checks text
            self.checks_text.configure(state="normal")
            self.checks_text.delete("1.0", "end")
            self.checks_text.insert(
                "end", "No document validations processed.\n", "issue"
            )
            self.checks_text.configure(state="disabled")

    def on_doc_combo_select(self, event):
        selected_name = self.doc_selector_var.get()
        if not self.selected_claim:
            return

        documents = self.selected_claim.get("documents") or []
        for doc in documents:
            if doc.get("file_name") == selected_name:
                self.load_selected_pdf_document(doc)
                break

    def load_selected_pdf_document(self, doc_dict):
        # 1. Clear trees
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)

        # Populate GPT Extracted fields
        ext_data = doc_dict.get("extracted_data") or {}
        for k, v in ext_data.items():
            self.doc_tree.insert("", "end", values=(k, str(v)))

        # Populate Validation list
        self.checks_text.configure(state="normal")
        self.checks_text.delete("1.0", "end")

        # Status Header
        self.checks_text.insert(
            "end",
            f"Document Class: {doc_dict.get('file_type') or 'UNKNOWN'}\n",
            "title",
        )
        self.checks_text.insert(
            "end", f"File Name: {doc_dict.get('file_name')}\n\n", "title"
        )

        validations = doc_dict.get("validations") or {}
        if validations:
            self.checks_text.insert("end", "Processed Verification Rules:\n", "title")
            for rule_name, rule_res in validations.items():
                res_str = str(rule_res)
                self.checks_text.insert("end", f"  • {rule_name}: ")

                # Check for Match vs Mismatch
                res_upper = res_str.upper()
                if (
                    "MATCH" in res_upper
                    or "VALID" in res_upper
                    or "OK" in res_upper
                    or "TRUE" in res_upper
                ):
                    self.checks_text.insert("end", f"{res_str}\n", "match")
                elif (
                    "MISMATCH" in res_upper
                    or "INVALID" in res_upper
                    or "FAILED" in res_upper
                    or "FALSE" in res_upper
                ):
                    self.checks_text.insert("end", f"{res_str}\n", "mismatch")
                else:
                    self.checks_text.insert("end", f"{res_str}\n")
        else:
            self.checks_text.insert(
                "end",
                "No specific validation checks rules performed on this document type.\n",
                "issue",
            )

        # Also print any row-level hold issues if they exist
        row_issues = self.selected_claim.get("issues") or []
        if row_issues:
            self.checks_text.insert(
                "end", "\nOverall Row HOLD Issues / Mismatches:\n", "title"
            )
            for issue in row_issues:
                self.checks_text.insert("end", f"  ⚠ {issue}\n", "mismatch")

        self.checks_text.configure(state="disabled")

        # Load visual confirmations (NEW!)
        self.load_visual_confirmations(doc_dict)

        # 2. Render PDF on Canvas
        pdf_path = doc_dict.get("file_path")
        if pdf_path and os.path.exists(pdf_path):
            try:
                # Close previous if exists
                if self.current_pdf_doc:
                    self.current_pdf_doc.close()
                self.current_pdf_path = pdf_path
                self.current_pdf_doc = fitz.open(pdf_path)
                self.current_pdf_page = 0
                self.render_pdf_page()
            except Exception as e:
                logging.error(f"Failed to open PDF document {pdf_path}: {e}")
                self.pdf_canvas.delete("all")
                self.page_label.config(text="Render Error")
        else:
            self.pdf_canvas.delete("all")
            self.page_label.config(text="File Not Found")

    def render_pdf_page(self):
        if not self.current_pdf_doc:
            return

        try:
            page = self.current_pdf_doc.load_page(self.current_pdf_page)

            # Setup Zoom matrix
            mat = fitz.Matrix(self.current_zoom, self.current_zoom)
            pix = page.get_pixmap(matrix=mat)

            # Render using PIL
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.canvas_photo = ImageTk.PhotoImage(img)

            self.pdf_canvas.delete("all")
            self.pdf_canvas.create_image(0, 0, anchor="nw", image=self.canvas_photo)

            # Configure scrolling boundaries
            self.pdf_canvas.configure(scrollregion=(0, 0, pix.width, pix.height))

            # Update toolbar indicators
            total = len(self.current_pdf_doc)
            self.page_label.config(text=f"Page {self.current_pdf_page + 1} of {total}")
            self.zoom_lbl.config(text=f"{int(self.current_zoom * 100)}%")
        except Exception as e:
            logging.error(f"Error rendering PDF page: {e}")

    def prev_pdf_page(self):
        if self.current_pdf_doc and self.current_pdf_page > 0:
            self.current_pdf_page -= 1
            self.render_pdf_page()

    def next_pdf_page(self):
        if (
            self.current_pdf_doc
            and self.current_pdf_page < len(self.current_pdf_doc) - 1
        ):
            self.current_pdf_page += 1
            self.render_pdf_page()

    def zoom_in_pdf(self):
        if self.current_pdf_doc and self.current_zoom < 3.0:
            self.current_zoom += 0.15
            self.render_pdf_page()

    def zoom_out_pdf(self):
        if self.current_pdf_doc and self.current_zoom > 0.4:
            self.current_zoom -= 0.15
            self.render_pdf_page()

    def run_east_disclaimer_analysis(self):
        if not hasattr(self, 'current_pdf_path') or not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            messagebox.showwarning("No PDF", "Please select a valid disclaimer PDF first.")
            return
            
        self.east_analyze_btn.config(state="disabled")
        self.east_status_lbl.config(text="Analyzing via OpenAI... please wait.")
        
        # Clear existing elements
        for widget in self.east_frame.winfo_children():
            widget.destroy()
            
        def task():
            try:
                import east_welcome_bonus_disclaimer
                results = east_welcome_bonus_disclaimer.process_east_welcome_bonus_disclaimer(self.current_pdf_path)
                self.after(0, self.display_east_disclaimer_results, results)
            except Exception as e:
                logging.error(f"Error in east disclaimer analysis: {e}")
                self.after(0, lambda: self.east_status_lbl.config(text=f"Error: {e}"))
                self.after(0, lambda: self.east_analyze_btn.config(state="normal"))
                
        threading.Thread(target=task, daemon=True).start()
        
    def display_east_disclaimer_results(self, results):
        self.east_analyze_btn.config(state="normal")
        self.east_status_lbl.config(text="Analysis complete.")
        
        # Keep references to PhotoImages to prevent garbage collection
        self.east_photo_images = getattr(self, 'east_photo_images', [])
        self.east_photo_images.clear()
        
        for idx, item in enumerate(results):
            card = tk.Frame(self.east_frame, bg="#ffffff", bd=1, relief="solid")
            card.pack(fill="x", pady=5, padx=5)
            
            # Header
            hdr = tk.Frame(card, bg="#f0f0f0")
            hdr.pack(fill="x", padx=2, pady=2)
            tk.Label(hdr, text=item.get("field", f"Field {idx+1}"), bg="#f0f0f0", font=("Segoe UI", 9, "bold")).pack(side="left")
            
            # Image Crop
            b64 = item.get("crop_b64")
            if b64:
                try:
                    img_data = base64.b64decode(b64)
                    pil_img = Image.open(io.BytesIO(img_data))
                    
                    # Scale down if too large
                    max_width = 400
                    if pil_img.width > max_width:
                        ratio = max_width / pil_img.width
                        new_h = int(pil_img.height * ratio)
                        pil_img = pil_img.resize((max_width, new_h), Image.LANCZOS)
                        
                    photo = ImageTk.PhotoImage(pil_img)
                    self.east_photo_images.append(photo)
                    tk.Label(card, image=photo, bg="#ffffff").pack(pady=2)
                except Exception as e:
                    logging.warning(f"Failed to display crop: {e}")
            
            # Value
            val = item.get("value", "")
            val_lbl = tk.Message(card, text=val, bg="#ffffff", width=400, font=("Segoe UI", 10))
            val_lbl.pack(pady=2, padx=5, fill="x")

    # Load local history registry
    def load_history_from_file(self):
        history_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "ui_history.json"
        )
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    self.processed_claims = json.load(f)

                # Populate Tree
                for row_result in self.processed_claims:
                    status_tag = (
                        "approved" if row_result["status"] == "APPROVED" else "hold"
                    )
                    self.history_tree.insert(
                        "",
                        "end",
                        values=(
                            f"Row {row_result['row_idx'] + 1}",
                            row_result["customer_name"],
                            row_result["status"],
                        ),
                        tags=(status_tag,),
                    )
            except Exception as e:
                logging.error(f"Failed to load history file: {e}")

    # Visual Confirmations Display Methods (NEW!)
    def load_visual_confirmations(self, doc_dict):
        """Display visual confirmations for selected document."""
        logging.info("[UI] load_visual_confirmations called")

        # Clear existing
        for widget in self.visual_frame.winfo_children():
            widget.destroy()
        self.extraction_images = []

        extracted_data = doc_dict.get("extracted_data", {})
        visual_data = extracted_data.get("visual_extractions", {})

        logging.info(f"[UI] Visual data has {len(visual_data)} fields")

        if not visual_data:
            logging.warning("[UI] No visual_extractions in document data")
            tk.Label(
                self.visual_frame,
                text="👁️ No visual data\navailable for this\ndocument\n\n(Process a NEW claim\nafter the update)",
                fg=TEXT_LIGHT_COLOR,
                bg=BG_COLOR,
                font=("Segoe UI", 10),
                justify=tk.CENTER,
            ).pack(pady=40)
            return

        # Display each visual extraction
        logging.info(f"[UI] Creating visual cards for: {list(visual_data.keys())}")
        for field_name, extraction in visual_data.items():
            try:
                self.create_visual_card(field_name, extraction)
                logging.info(f"[UI] Created card for {field_name}")
            except Exception as e:
                logging.error(f"[UI] Failed to create card for {field_name}: {e}")

        logging.info(
            f"[UI] Visual confirmations loaded: {len(self.extraction_images)} images"
        )

    def create_visual_card(self, field_name, extraction):
        """Create a card showing one visual extraction."""
        # Card container
        card = tk.Frame(
            self.visual_frame, bg=CARD_BG_COLOR, relief=tk.RAISED, borderwidth=1
        )
        card.pack(fill=tk.X, padx=8, pady=6)

        # Header with field name
        header = tk.Frame(card, bg="#2A2A2A")
        header.pack(fill=tk.X)

        # Emoji mapping
        emoji_map = {
            "seal_stamp_dealer_name": "🏢 Dealer Stamp",
            "customer_signature": "✍️ Customer Signature",
            "dealer_signature": "✍️ Dealer Signature",
            "invoice_number": "📄 Invoice Number",
            "chassis_number": "🚗 Chassis Number",
            "invoice_date": "📅 Invoice Date",
            "customer_name": "👤 Customer Name",
            "registration_number": "🚙 Registration",
            "welcome_bonus_amount": "🎁 Welcome Bonus",
            "dealership_name": "🏪 Dealership Name",
            "document_type": "📑 Document Type",
        }

        title = emoji_map.get(field_name, field_name.replace("_", " ").title())

        tk.Label(
            header,
            text=title,
            font=("Segoe UI", 9, "bold"),
            fg=TEXT_COLOR,
            bg="#2A2A2A",
        ).pack(side=tk.LEFT, padx=10, pady=6)

        # Confidence badge
        confidence = extraction.get("confidence", 0)
        if confidence >= 80:
            badge_color = SUCCESS_COLOR
        elif confidence >= 60:
            badge_color = WARNING_COLOR
        else:
            badge_color = ERROR_COLOR

        tk.Label(
            header,
            text=f"{confidence}%",
            font=("Segoe UI", 9, "bold"),
            fg=badge_color,
            bg="#2A2A2A",
        ).pack(side=tk.RIGHT, padx=10, pady=6)

        # Body
        body = tk.Frame(card, bg=CARD_BG_COLOR)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Display cropped image
        image_b64 = extraction.get("image_base64")
        logging.info(f"[UI] {field_name} has image: {bool(image_b64)}")

        if image_b64:
            try:
                logging.info(
                    f"[UI] Decoding {field_name} image ({len(image_b64)} bytes)"
                )
                # Decode and display
                image_bytes = base64.b64decode(image_b64)
                image = Image.open(io.BytesIO(image_bytes))
                logging.info(f"[UI] Image size: {image.size}")

                # Resize to fit (max 340x180)
                image.thumbnail((340, 180), Image.Resampling.LANCZOS)
                logging.info(f"[UI] Resized to: {image.size}")

                photo = ImageTk.PhotoImage(image)
                self.extraction_images.append(photo)  # Keep reference
                logging.info(f"[UI] Created PhotoImage for {field_name}")

                img_label = tk.Label(body, image=photo, bg=CARD_BG_COLOR)
                img_label.pack(pady=(0, 8))
                logging.info(f"[UI] ✓ Successfully displayed {field_name} image")
            except Exception as e:
                logging.error(f"[UI] Error displaying image for {field_name}: {e}")
                import traceback

                traceback.print_exc()
                tk.Label(
                    body,
                    text=f"⚠️ Image decode error\n{str(e)}",
                    fg=ERROR_COLOR,
                    bg=CARD_BG_COLOR,
                    font=("Segoe UI", 8),
                ).pack()
        else:
            logging.warning(f"[UI] No image_base64 for {field_name}")
            tk.Label(
                body, text="⚠️ No image data", fg=WARNING_COLOR, bg=CARD_BG_COLOR
            ).pack()

        # Display extracted value
        value = extraction.get("value", "N/A")
        if (
            value
            and str(value).strip()
            and str(value).strip().lower() not in ["null", "none", "n/a"]
        ):
            value_frame = tk.Frame(body, bg="#1E1E1E", relief=tk.FLAT)
            value_frame.pack(fill=tk.X)

            tk.Label(
                value_frame,
                text=f"Value: {value}",
                font=("Segoe UI", 9),
                fg=TEXT_COLOR,
                bg="#1E1E1E",
                wraplength=320,
                justify=tk.LEFT,
            ).pack(padx=8, pady=6, anchor="w")

    # FAB Panel Minimizing Toggles
    def create_fab_window(self):
        self.fab_window = tk.Toplevel(self)
        self.fab_window.title("KYC FAB")
        # Remove windows border frame decor
        self.fab_window.overrideredirect(True)
        # Keep on top of all screens
        self.fab_window.wm_attributes("-topmost", True)
        # Set size
        self.fab_window.geometry("70x70+20+20")
        self.fab_window.configure(bg="#1E1E1E")

        # Transparent canvas background (visual simulation)
        canvas = tk.Canvas(
            self.fab_window, width=70, height=70, bg="#1E1E1E", highlightthickness=0
        )
        canvas.pack(fill="both", expand=True)

        # Draw a beautiful circle
        circle = canvas.create_oval(
            5,
            5,
            65,
            65,
            fill="#2563EB",
            outline="#60A5FA",
            width=3,
            activefill="#3B82F6",
        )
        text = canvas.create_text(
            35, 35, text="KYC", fill="#FFFFFF", font=("Segoe UI", 11, "bold")
        )

        # Click circle action button restores UI
        canvas.tag_bind(circle, "<Button-1>", self.restore_from_fab)
        canvas.tag_bind(text, "<Button-1>", self.restore_from_fab)

        # Make FAB draggable
        self.fab_window.x = 0
        self.fab_window.y = 0

        def start_drag(event):
            self.fab_window.x = event.x
            self.fab_window.y = event.y

        def drag(event):
            dx = event.x - self.fab_window.x
            dy = event.y - self.fab_window.y
            new_x = self.fab_window.winfo_x() + dx
            new_y = self.fab_window.winfo_y() + dy
            # Keep boundaries on screen
            self.fab_window.geometry(f"+{new_x}+{new_y}")

        canvas.bind("<Button-1>", start_drag)
        canvas.bind("<B1-Motion>", drag)

        # Start hidden
        self.fab_window.withdraw()

    def minimize_to_fab(self):
        # Hide main window
        self.withdraw()
        # Show FAB
        self.fab_window.deiconify()

    def restore_from_fab(self, event=None):
        # Hide FAB
        self.fab_window.withdraw()
        # Restore main window
        self.deiconify()


if __name__ == "__main__":
    app = AppUI()

    # Handle window close cleanly
    def on_closing():
        if app.current_pdf_doc:
            try:
                app.current_pdf_doc.close()
            except Exception:
                pass
        app.destroy()
        sys.exit(0)

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()
