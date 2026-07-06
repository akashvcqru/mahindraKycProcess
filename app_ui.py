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

try:
    from dotenv import load_dotenv
    import sys
    import os
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(application_path, '.env'))
except ImportError:
    pass

# Monkeypatch requests to support Claude as a drop-in replacement for OpenAI
import requests
import json
import time

original_post = requests.post

def transform_openai_to_claude(openai_json):
    claude_messages = []
    messages = openai_json.get("messages", [])
    system_text = None
    
    for msg in messages:
        role = msg.get("role", "user")
        content_in = msg.get("content")
        
        if role == "system":
            if isinstance(content_in, str):
                system_text = (system_text + "\n" + content_in) if system_text else content_in
            elif isinstance(content_in, list):
                text_parts = [p.get("text", "") for p in content_in if p.get("type") == "text"]
                combined = " ".join(text_parts)
                system_text = (system_text + "\n" + combined) if system_text else combined
            continue
            
        claude_content = []
        if isinstance(content_in, list):
            for part in content_in:
                if part.get("type") == "text":
                    claude_content.append({
                        "type": "text",
                        "text": part.get("text")
                    })
                elif part.get("type") == "image_url":
                    img_url = part.get("image_url", {}).get("url", "")
                    if img_url.startswith("data:image/"):
                        try:
                            header, base64_data = img_url.split(",", 1)
                            media_type = header.split(";")[0].replace("data:", "")
                        except Exception:
                            base64_data = img_url
                            media_type = "image/jpeg"
                    else:
                        base64_data = img_url
                        media_type = "image/jpeg"
                    
                    claude_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data
                        }
                    })
        elif isinstance(content_in, str):
            claude_content = content_in
            
        claude_messages.append({
            "role": role,
            "content": claude_content
        })
        
    claude_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    claude_payload = {
        "model": claude_model,
        "max_tokens": openai_json.get("max_tokens", 4096),
        "messages": claude_messages
    }
    if system_text:
        claude_payload["system"] = system_text
        
    return claude_payload

def transform_claude_to_openai(claude_json):
    text_content = ""
    for part in claude_json.get("content", []):
        if part.get("type") == "text":
            text_content += part.get("text", "")
            
    # Extract JSON if present to conform with OpenAI strict JSON format expectations
    clean_content = text_content.strip()
    if '{' in clean_content or '[' in clean_content:
        start_brace = clean_content.find('{')
        start_bracket = clean_content.find('[')
        
        start = -1
        end = -1
        
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            start = start_brace
            end = clean_content.rfind('}')
        elif start_bracket != -1:
            start = start_bracket
            end = clean_content.rfind(']')
            
        if start != -1 and end != -1 and end > start:
            json_candidate = clean_content[start:end+1]
            try:
                # Validate it's parseable JSON
                json.loads(json_candidate)
                text_content = json_candidate
            except json.JSONDecodeError:
                pass
            
    openai_json = {
        "id": claude_json.get("id", "chatcmpl-mock"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": claude_json.get("model", "gpt-4o"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text_content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": claude_json.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": claude_json.get("usage", {}).get("output_tokens", 0),
            "total_tokens": claude_json.get("usage", {}).get("input_tokens", 0) + claude_json.get("usage", {}).get("output_tokens", 0)
        }
    }
    return openai_json

def custom_post(url, *args, **kwargs):
    if url == "https://api.openai.com/v1/chat/completions":
        provider = os.getenv("AI_PROVIDER", "OpenAI")
        if provider == "Claude":
            claude_key = os.getenv("CLAUDE_API_KEY", "")
            headers = {
                "x-api-key": claude_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            openai_payload = kwargs.get("json", {})
            claude_payload = transform_openai_to_claude(openai_payload)
            timeout = kwargs.get("timeout", 60)
            
            logging.info("Routing request to Claude API...")
            claude_resp = original_post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=claude_payload,
                timeout=timeout
            )
            
            resp = requests.Response()
            resp.status_code = claude_resp.status_code
            resp.headers = dict(claude_resp.headers)
            resp.reason = claude_resp.reason
            resp.url = claude_resp.url
            resp.request = claude_resp.request
            
            if claude_resp.status_code == 200:
                try:
                    claude_json = claude_resp.json()
                    openai_json = transform_claude_to_openai(claude_json)
                    resp._content = json.dumps(openai_json).encode("utf-8")
                except Exception as e:
                    logging.error(f"Error parsing Claude response: {e}")
                    resp._content = claude_resp.content
            else:
                logging.error(f"Claude API request failed ({claude_resp.status_code}): {claude_resp.text}")
                resp._content = claude_resp.content
                
            return resp
            
    return original_post(url, *args, **kwargs)

requests.post = custom_post

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

        # VS Code style sidebar (width=60)
        self.sidebar_frame = tk.Frame(self, bg="#1E1E1E", width=60)
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # Workspace pane container
        self.workspace_pane = tk.PanedWindow(
            self, orient="horizontal", bg=BG_COLOR, bd=0, sashwidth=6, sashrelief="flat"
        )
        self.workspace_pane.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Sidebar buttons
        self.panel_states = {
            "params": True,
            "console": True,
            "history": True,
            "document": True,
            "visual": True,
        }

        self.sidebar_buttons = {}
        button_info = [
            ("params", "⚙️\nParams"),
            ("console", "💻\nConsole"),
            ("history", "📜\nHistory"),
            ("document", "📑\nDoc"),
            ("visual", "🔍\nVisual"),
        ]

        for key, text in button_info:
            btn = tk.Button(
                self.sidebar_frame,
                text=text,
                bg="#1E1E1E",
                fg=TEXT_LIGHT_COLOR,
                activebackground=ACCENT_COLOR,
                activeforeground="#FFFFFF",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                bd=0,
                pady=15,
                command=lambda k=key: self.toggle_panel(k)
            )
            btn.pack(fill="x", pady=2)
            self.sidebar_buttons[key] = btn

        # Start panel controls card
        self.controls_card = tk.LabelFrame(
            self,
            text="Automation Parameters",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=15,
            relief="solid",
            bd=1,
        )

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

        # Date Selection Choice
        tk.Label(
            self.controls_card,
            text="Date Range Option:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=2, column=0, sticky="w", pady=6)
        self.date_choice_var = tk.StringVar(value="Current Month")
        self.date_choice_combo = ttk.Combobox(
            self.controls_card,
            textvariable=self.date_choice_var,
            values=["Current Month", "Testing (1 Jun - 30 Jun)"],
            state="readonly",
            width=18,
        )
        self.date_choice_combo.grid(row=2, column=1, sticky="w", padx=10, pady=6)

        # Rows Limit Bounds Option
        tk.Label(
            self.controls_card,
            text="Row Bounds Limit:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=3, column=0, sticky="w", pady=6)
        self.row_limit_var = tk.StringVar(value="a")
        self.row_limit_combo = ttk.Combobox(
            self.controls_card,
            textvariable=self.row_limit_var,
            values=["a", "1", "2", "3", "4", "5", "1,3,5", "2-4"],
            state="normal",
            width=18,
        )
        self.row_limit_combo.grid(row=3, column=1, sticky="w", padx=10, pady=6)

        # Scheme Type Choice
        tk.Label(
            self.controls_card,
            text="Scheme Type Mode:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=4, column=0, sticky="w", pady=6)
        self.scheme_type_var = tk.StringVar(value="Welcome Bonus Scheme")
        self.scheme_type_combo = ttk.Combobox(
            self.controls_card,
            textvariable=self.scheme_type_var,
            values=["Welcome Bonus Scheme", "Scrappage Bonus Scheme"],
            state="readonly",
            width=18,
        )
        self.scheme_type_combo.grid(row=4, column=1, sticky="w", padx=10, pady=6)

        # Helper text for custom rows
        self.row_helper_lbl = tk.Label(
            self.controls_card,
            text="* Type custom rows e.g. 1,3,5 or 2-4",
            bg=CARD_BG_COLOR,
            fg=TEXT_LIGHT_COLOR,
            font=("Segoe UI", 8, "italic"),
        )
        self.row_helper_lbl.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 4))

        # AI Provider selection variable and UI (NEW!)
        self.ai_provider_var = tk.StringVar(value=os.getenv("AI_PROVIDER", "OpenAI"))
        self.openai_key_var = tk.StringVar(value=os.getenv("OPENAI_API_KEY", ""))
        self.claude_key_var = tk.StringVar(value=os.getenv("CLAUDE_API_KEY", ""))

        tk.Label(
            self.controls_card,
            text="AI Provider Selector:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=6, column=0, sticky="w", pady=6)
        self.ai_provider_combo = ttk.Combobox(
            self.controls_card,
            textvariable=self.ai_provider_var,
            values=["OpenAI", "Claude"],
            state="readonly",
            width=18,
        )
        self.ai_provider_combo.grid(row=6, column=1, sticky="w", padx=10, pady=6)

        # OpenAI API Key field
        tk.Label(
            self.controls_card,
            text="OpenAI API Key:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=7, column=0, sticky="w", pady=6)
        self.openai_key_entry = tk.Entry(
            self.controls_card,
            textvariable=self.openai_key_var,
            show="*",
            bg="#2A2A2A",
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            font=("Segoe UI", 9),
            relief="flat",
            bd=1,
            width=21,
        )
        self.openai_key_entry.grid(row=7, column=1, sticky="w", padx=10, pady=6)

        # Claude API Key field
        tk.Label(
            self.controls_card,
            text="Claude API Key:",
            bg=CARD_BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=8, column=0, sticky="w", pady=6)
        self.claude_key_entry = tk.Entry(
            self.controls_card,
            textvariable=self.claude_key_var,
            show="*",
            bg="#2A2A2A",
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            font=("Segoe UI", 9),
            relief="flat",
            bd=1,
            width=21,
        )
        self.claude_key_entry.grid(row=8, column=1, sticky="w", padx=10, pady=6)

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
        self.start_btn.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # Real-time styled terminal console logs log widget
        self.log_card = tk.LabelFrame(
            self,
            text="Real-time Execution Console",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 10, "bold"),
            relief="solid",
            bd=1,
        )

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
        # Row History Treeview Panel (Left side)
        self.history_frame = tk.LabelFrame(
            self,
            text="Processed Rows History",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 10, "bold"),
            relief="solid",
            bd=1,
            width=280,
        )
        self.history_frame.pack_propagate(False)

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
        self.viewer_frame = tk.Frame(self, bg=BG_COLOR)

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

        # Tab 5: East Welcome Bonus Ledger
        self.tab_east_ledger = tk.Frame(self.details_notebook, bg=CARD_BG_COLOR)
        self.details_notebook.add(self.tab_east_ledger, text="East Welcome Ledger")
        
        self.east_ledger_top_frame = tk.Frame(self.tab_east_ledger, bg=CARD_BG_COLOR)
        self.east_ledger_top_frame.pack(fill="x", padx=5, pady=5)
        
        self.east_ledger_analyze_btn = tk.Button(self.east_ledger_top_frame, text="Analyze Ledger (OpenAI)", bg="#667eea", fg="white", font=("Segoe UI", 10, "bold"), command=self.run_east_ledger_analysis)
        self.east_ledger_analyze_btn.pack(side="left")
        
        self.east_ledger_status_lbl = tk.Label(self.east_ledger_top_frame, text="", bg=CARD_BG_COLOR, fg=TEXT_COLOR)
        self.east_ledger_status_lbl.pack(side="left", padx=10)

        self.east_ledger_canvas = tk.Canvas(self.tab_east_ledger, bg=CARD_BG_COLOR, highlightthickness=0)
        self.east_ledger_scroll = ttk.Scrollbar(self.tab_east_ledger, orient="vertical", command=self.east_ledger_canvas.yview)
        self.east_ledger_scroll.pack(side="right", fill="y")
        self.east_ledger_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.east_ledger_canvas.configure(yscrollcommand=self.east_ledger_scroll.set)
        
        self.east_ledger_frame = tk.Frame(self.east_ledger_canvas, bg=CARD_BG_COLOR)
        self.east_ledger_canvas.create_window((0, 0), window=self.east_ledger_frame, anchor="nw")
        
        def on_east_ledger_frame_configure(event):
            self.east_ledger_canvas.configure(scrollregion=self.east_ledger_canvas.bbox("all"))
            
        self.east_ledger_frame.bind("<Configure>", on_east_ledger_frame_configure)

        # Tab 6: East Welcome Bonus Invoice
        self.tab_east_invoice = tk.Frame(self.details_notebook, bg=CARD_BG_COLOR)
        self.details_notebook.add(self.tab_east_invoice, text="East Welcome Invoice")
        
        self.east_invoice_top_frame = tk.Frame(self.tab_east_invoice, bg=CARD_BG_COLOR)
        self.east_invoice_top_frame.pack(fill="x", padx=5, pady=5)
        
        self.east_invoice_analyze_btn = tk.Button(self.east_invoice_top_frame, text="Analyze Invoice (OpenAI)", bg="#667eea", fg="white", font=("Segoe UI", 10, "bold"), command=self.run_east_invoice_analysis)
        self.east_invoice_analyze_btn.pack(side="left")
        
        self.east_invoice_status_lbl = tk.Label(self.east_invoice_top_frame, text="", bg=CARD_BG_COLOR, fg=TEXT_COLOR)
        self.east_invoice_status_lbl.pack(side="left", padx=10)

        self.east_invoice_canvas = tk.Canvas(self.tab_east_invoice, bg=CARD_BG_COLOR, highlightthickness=0)
        self.east_invoice_scroll = ttk.Scrollbar(self.tab_east_invoice, orient="vertical", command=self.east_invoice_canvas.yview)
        self.east_invoice_scroll.pack(side="right", fill="y")
        self.east_invoice_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.east_invoice_canvas.configure(yscrollcommand=self.east_invoice_scroll.set)
        
        self.east_invoice_frame = tk.Frame(self.east_invoice_canvas, bg=CARD_BG_COLOR)
        self.east_invoice_canvas.create_window((0, 0), window=self.east_invoice_frame, anchor="nw")
        
        def on_east_invoice_frame_configure(event):
            self.east_invoice_canvas.configure(scrollregion=self.east_invoice_canvas.bbox("all"))
            
        self.east_invoice_frame.bind("<Configure>", on_east_invoice_frame_configure)



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
            self,
            text="🔍 Visual Confirmations",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 10, "bold"),
            relief="solid",
            bd=1,
            width=380,
        )
        self.visual_panel.pack_propagate(False)

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

        self.panel_widgets = {
            "params": self.controls_card,
            "console": self.log_card,
            "history": self.history_frame,
            "document": self.viewer_frame,
            "visual": self.visual_panel,
        }

        self.update_workspace_layout()

    def toggle_panel(self, key):
        self.panel_states[key] = not self.panel_states[key]
        self.update_workspace_layout()

    def update_workspace_layout(self):
        # 1. Forget all currently active panes
        for pane in self.workspace_pane.panes():
            self.workspace_pane.forget(pane)

        # 2. Add active ones in correct order
        order = ["params", "console", "history", "document", "visual"]
        minsizes = {
            "params": 280,
            "console": 350,
            "history": 280,
            "document": 600,
            "visual": 300
        }

        for key in order:
            widget = self.panel_widgets[key]
            if self.panel_states[key]:
                try:
                    widget.pack_forget()
                    widget.grid_forget()
                except Exception:
                    pass
                self.workspace_pane.add(widget, minsize=minsizes[key])

            # 3. Update button color based on state
            btn = self.sidebar_buttons[key]
            if self.panel_states[key]:
                btn.config(bg=ACCENT_COLOR, fg="#FFFFFF")
            else:
                btn.config(bg="#1E1E1E", fg=TEXT_LIGHT_COLOR)

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
    def update_env_keys(self):
        provider = self.ai_provider_var.get()
        openai_key = self.openai_key_var.get().strip()
        claude_key = self.claude_key_var.get().strip()
        
        os.environ["AI_PROVIDER"] = provider
        os.environ["OPENAI_API_KEY"] = openai_key
        os.environ["CLAUDE_API_KEY"] = claude_key
        
        # Save to .env file
        try:
            if getattr(sys, 'frozen', False):
                application_path = os.path.dirname(sys.executable)
            else:
                application_path = os.path.dirname(os.path.abspath(__file__))
            env_path = os.path.join(application_path, '.env')
            
            lines = []
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            
            new_lines = []
            updated = {"AI_PROVIDER": False, "OPENAI_API_KEY": False, "CLAUDE_API_KEY": False}
            for line in lines:
                striped = line.strip()
                if not striped or striped.startswith('#'):
                    new_lines.append(line)
                    continue
                if '=' in striped:
                    k, v = striped.split('=', 1)
                    k = k.strip()
                    if k in updated:
                        if k == "AI_PROVIDER":
                            new_lines.append(f"AI_PROVIDER={provider}\n")
                        elif k == "OPENAI_API_KEY":
                            new_lines.append(f"OPENAI_API_KEY={openai_key}\n")
                        elif k == "CLAUDE_API_KEY":
                            new_lines.append(f"CLAUDE_API_KEY={claude_key}\n")
                        updated[k] = True
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            if not updated["AI_PROVIDER"]:
                new_lines.append(f"AI_PROVIDER={provider}\n")
            if not updated["OPENAI_API_KEY"]:
                new_lines.append(f"OPENAI_API_KEY={openai_key}\n")
            if not updated["CLAUDE_API_KEY"]:
                new_lines.append(f"CLAUDE_API_KEY={claude_key}\n")
                
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        except Exception as e:
            logging.error(f"Failed to save .env file: {e}")

    def check_keys(self):
        self.update_env_keys()
        provider = self.ai_provider_var.get()
        if provider == "OpenAI" and not self.openai_key_var.get().strip():
            messagebox.showerror("Error", "OpenAI API Key is required.")
            return False
        elif provider == "Claude" and not self.claude_key_var.get().strip():
            messagebox.showerror("Error", "Claude API Key is required.")
            return False
        return True

    def start_automation(self):
        if self.automation_thread and self.automation_thread.is_alive():
            messagebox.showwarning("Running", "Automation is already in progress.")
            return

        if not self.check_keys():
            return

        # Disable controls during run
        self.start_btn.configure(
            state="disabled", text="RUNNING PROCESS...", bg="#4B5563"
        )
        self.login_mode_combo.configure(state="disabled")
        self.claim_choice_combo.configure(state="disabled")
        self.date_choice_combo.configure(state="disabled")
        self.row_limit_combo.configure(state="disabled")
        self.scheme_type_combo.configure(state="disabled")
        self.ai_provider_combo.configure(state="disabled")
        self.openai_key_entry.configure(state="disabled")
        self.claude_key_entry.configure(state="disabled")

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
        date_range_choice = self.date_choice_var.get()
        force_scheme = "scrappage" if self.scheme_type_var.get() == "Scrappage Bonus Scheme" else "welcome"

        try:
            automate_login.main(
                use_existing_login=login_choice,
                target_claim_choice=claim_choice,
                row_limit=row_limit,
                date_range_choice=date_range_choice,
                force_scheme=force_scheme
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
        self.date_choice_combo.configure(state="readonly")
        self.row_limit_combo.configure(state="normal")
        self.scheme_type_combo.configure(state="readonly")
        self.ai_provider_combo.configure(state="readonly")
        self.openai_key_entry.configure(state="normal")
        self.claude_key_entry.configure(state="normal")

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

        if not self.check_keys():
            return
            
        self.east_analyze_btn.config(state="disabled")
        self.east_status_lbl.config(text=f"Analyzing via {self.ai_provider_var.get()}... please wait.")
        
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

    def run_east_ledger_analysis(self):
        if not hasattr(self, 'current_pdf_path') or not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            messagebox.showwarning("No PDF", "Please select a valid ledger PDF first.")
            return

        if not self.check_keys():
            return
            
        self.east_ledger_analyze_btn.config(state="disabled")
        self.east_ledger_status_lbl.config(text=f"Analyzing via {self.ai_provider_var.get()}... please wait.")
        
        # Clear existing elements
        for widget in self.east_ledger_frame.winfo_children():
            widget.destroy()
            
        def task():
            try:
                import east_welcome_bonus_ledger
                results = east_welcome_bonus_ledger.process_east_welcome_bonus_ledger(self.current_pdf_path)
                self.after(0, self.display_east_ledger_results, results)
            except Exception as e:
                logging.error(f"Error in east ledger analysis: {e}")
                self.after(0, lambda: self.east_ledger_status_lbl.config(text=f"Error: {e}"))
                self.after(0, lambda: self.east_ledger_analyze_btn.config(state="normal"))
                
        threading.Thread(target=task, daemon=True).start()
        
    def display_east_ledger_results(self, results):
        self.east_ledger_analyze_btn.config(state="normal")
        self.east_ledger_status_lbl.config(text="Analysis complete.")
        
        # Keep references to PhotoImages to prevent garbage collection
        self.east_ledger_photo_images = getattr(self, 'east_ledger_photo_images', [])
        self.east_ledger_photo_images.clear()
        
        for idx, item in enumerate(results):
            card = tk.Frame(self.east_ledger_frame, bg="#ffffff", bd=1, relief="solid")
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
                    self.east_ledger_photo_images.append(photo)
                    tk.Label(card, image=photo, bg="#ffffff").pack(pady=2)
                except Exception as e:
                    logging.warning(f"Failed to display crop: {e}")
            
            # Value
            val = item.get("value", "")
            val_lbl = tk.Message(card, text=val, bg="#ffffff", width=400, font=("Segoe UI", 10))
            val_lbl.pack(pady=2, padx=5, fill="x")

    def run_east_invoice_analysis(self):
        if not hasattr(self, 'current_pdf_path') or not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            messagebox.showwarning("No PDF", "Please select a valid invoice PDF first.")
            return

        if not self.check_keys():
            return
            
        self.east_invoice_analyze_btn.config(state="disabled")
        self.east_invoice_status_lbl.config(text=f"Analyzing via {self.ai_provider_var.get()}... please wait.")
        
        # Clear existing elements
        for widget in self.east_invoice_frame.winfo_children():
            widget.destroy()
            
        def task():
            try:
                import east_welcome_bonus_invoice
                results = east_welcome_bonus_invoice.process_east_welcome_bonus_invoice(self.current_pdf_path)
                self.after(0, self.display_east_invoice_results, results)
            except Exception as e:
                logging.error(f"Error in east invoice analysis: {e}")
                self.after(0, lambda: self.east_invoice_status_lbl.config(text=f"Error: {e}"))
                self.after(0, lambda: self.east_invoice_analyze_btn.config(state="normal"))
                
        threading.Thread(target=task, daemon=True).start()
        
    def display_east_invoice_results(self, results):
        self.east_invoice_analyze_btn.config(state="normal")
        self.east_invoice_status_lbl.config(text="Analysis complete.")
        
        # Keep references to PhotoImages to prevent garbage collection
        self.east_invoice_photo_images = getattr(self, 'east_invoice_photo_images', [])
        self.east_invoice_photo_images.clear()
        
        for idx, item in enumerate(results):
            card = tk.Frame(self.east_invoice_frame, bg="#ffffff", bd=1, relief="solid")
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
                    self.east_invoice_photo_images.append(photo)
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
        pdf_path = doc_dict.get("file_path", doc_dict.get("path", ""))
        doc_type = doc_dict.get("file_type", doc_dict.get("doc_type", "")).upper()
        
        is_ledger = False
        fname_lower = os.path.basename(pdf_path).lower()
        dict_fname_lower = doc_dict.get("file_name", "").lower()
        _ledger_prefixes = ("l-", "les", "ldgr", "lgr", "ldr", "ldg")
        if (doc_type == "LEDGER" or 
            "ledger" in fname_lower or 
            "ledger" in dict_fname_lower or 
            any(fname_lower.startswith(p) for p in _ledger_prefixes) or
            any(dict_fname_lower.startswith(p) for p in _ledger_prefixes)):
            is_ledger = True

        is_invoice = False
        _invoice_prefixes = ("inv",)
        _invoice_keywords = ("invoice",)
        if (doc_type == "INVOICE" or
            any(fname_lower.startswith(p) for p in _invoice_prefixes) or
            any(dict_fname_lower.startswith(p) for p in _invoice_prefixes) or
            any(k in fname_lower for k in _invoice_keywords) or
            any(k in dict_fname_lower for k in _invoice_keywords)):
            is_invoice = True
            
        if is_ledger and os.path.exists(pdf_path):
            logging.info(f"[UI] Intercepting LEDGER visual confirmations for {pdf_path}")
            
            # Show a loading label
            loading_lbl = tk.Label(
                self.visual_frame,
                text="⏳ Extracting Ledger fields...\nPlease wait (approx 5-10s)",
                fg=TEXT_LIGHT_COLOR,
                bg=BG_COLOR,
                font=("Segoe UI", 10),
                justify=tk.CENTER,
            )
            loading_lbl.pack(pady=40)
            
            def ledger_task():
                try:
                    current_scheme = self.scheme_type_var.get()
                    if current_scheme == "Scrappage Bonus Scheme":
                        import scrappage_scheme.ledger_validation as scrappage_ledger
                        ledger_results = scrappage_ledger.process_scrappage_ledger_visual(pdf_path)
                    else:
                        import east_welcome_bonus_ledger
                        ledger_results = east_welcome_bonus_ledger.process_east_welcome_bonus_ledger(pdf_path)
                    
                    visual_data = {}
                    for item in ledger_results:
                        field = item.get("field", "")
                        val = item.get("value", "")
                        crop = item.get("crop_b64", item.get("crop", ""))
                        if field:
                            visual_data[field] = {
                                "value": val,
                                "confidence": 95,
                                "image_base64": crop
                            }
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)
                except Exception as e:
                    logging.error(f"[UI] Ledger specific visual extraction failed: {e}")
                    # Fallback
                    visual_data = extracted_data.get("visual_extractions", {})
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)
                    
            import threading
            threading.Thread(target=ledger_task, daemon=True).start()
            return

        if is_invoice and os.path.exists(pdf_path):
            logging.info(f"[UI] Intercepting INVOICE visual confirmations for {pdf_path}")

            loading_lbl = tk.Label(
                self.visual_frame,
                text="⏳ Extracting Invoice fields...\nPlease wait (approx 5-10s)",
                fg=TEXT_LIGHT_COLOR,
                bg=BG_COLOR,
                font=("Segoe UI", 10),
                justify=tk.CENTER,
            )
            loading_lbl.pack(pady=40)

            def invoice_task():
                try:
                    import scrappage_scheme.invoice_validation as inv_mod
                    invoice_results = inv_mod.process_invoice_visual(pdf_path)

                    visual_data = {}
                    for item in invoice_results:
                        field = item.get("field", "")
                        val   = item.get("value", "")
                        crop  = item.get("crop_b64", item.get("crop", ""))
                        if field:
                            visual_data[field] = {
                                "value": val,
                                "confidence": 95,
                                "image_base64": crop,
                            }
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)
                except Exception as exc:
                    logging.error(f"[UI] Invoice visual extraction failed: {exc}")
                    visual_data = extracted_data.get("visual_extractions", {})
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)

            import threading
            threading.Thread(target=invoice_task, daemon=True).start()
            return

        is_cod = False
        _cod_prefixes = ("cod",)
        _cod_keywords = ("certificate of deposit", "cod")
        if (doc_type == "COD" or
            any(fname_lower.startswith(p) for p in _cod_prefixes) or
            any(dict_fname_lower.startswith(p) for p in _cod_prefixes) or
            any(k in fname_lower for k in _cod_keywords) or
            any(k in dict_fname_lower for k in _cod_keywords)):
            is_cod = True

        if is_cod and os.path.exists(pdf_path):
            logging.info(f"[UI] Intercepting COD visual confirmations for {pdf_path}")

            loading_lbl = tk.Label(
                self.visual_frame,
                text="⏳ Extracting Certificate fields...\nPlease wait (approx 5-10s)",
                fg=TEXT_LIGHT_COLOR,
                bg=BG_COLOR,
                font=("Segoe UI", 10),
                justify=tk.CENTER,
            )
            loading_lbl.pack(pady=40)

            def cod_task():
                try:
                    import scrappage_scheme.cod_validation as cod_mod
                    cod_results = cod_mod.process_cod_visual(pdf_path)

                    visual_data = {}
                    for item in cod_results:
                        field = item.get("field", "")
                        val   = item.get("value", "")
                        crop  = item.get("crop_b64", item.get("crop", ""))
                        if field:
                            visual_data[field] = {
                                "value": val,
                                "confidence": 95,
                                "image_base64": crop,
                            }
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)
                except Exception as exc:
                    logging.error(f"[UI] COD visual extraction failed: {exc}")
                    visual_data = extracted_data.get("visual_extractions", {})
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)

            import threading
            threading.Thread(target=cod_task, daemon=True).start()
            return

        is_oem = False
        _oem_prefixes = ("oem",)
        _oem_keywords = ("scrappage certificate", "oem")
        if (doc_type == "OEM" or
            any(fname_lower.startswith(p) for p in _oem_prefixes) or
            any(dict_fname_lower.startswith(p) for p in _oem_prefixes) or
            any(k in fname_lower for k in _oem_keywords) or
            any(k in dict_fname_lower for k in _oem_keywords)):
            is_oem = True

        if is_oem and os.path.exists(pdf_path):
            logging.info(f"[UI] Intercepting OEM visual confirmations for {pdf_path}")

            loading_lbl = tk.Label(
                self.visual_frame,
                text="⏳ Extracting Certificate fields...\nPlease wait (approx 5-10s)",
                fg=TEXT_LIGHT_COLOR,
                bg=BG_COLOR,
                font=("Segoe UI", 10),
                justify=tk.CENTER,
            )
            loading_lbl.pack(pady=40)

            def oem_task():
                try:
                    import scrappage_scheme.oem_document_validation as oem_mod
                    
                    claim_details = self.selected_claim.get("claim_details") or {}
                    old_vehicle_details = self.selected_claim.get("old_vehicle_details") or {}
                    
                    old_chassis = old_vehicle_details.get("Chassis No", "").strip()
                    old_reg = old_vehicle_details.get("Reg. No", old_vehicle_details.get("Reg No", old_vehicle_details.get("Registration No", ""))).strip()
                    if not old_reg:
                        old_reg = claim_details.get("Reg. No", claim_details.get("Reg No", claim_details.get("Registration No", ""))).strip()
                    new_chassis = claim_details.get("Chassis No", "").strip()

                    oem_results = oem_mod.process_oem_visual(
                        pdf_path,
                        old_chassis=old_chassis,
                        old_reg=old_reg,
                        new_chassis=new_chassis
                    )

                    visual_data = {}
                    for item in oem_results:
                        field = item.get("field", "")
                        val   = item.get("value", "")
                        crop  = item.get("crop_b64", item.get("crop", ""))
                        if field:
                            visual_data[field] = {
                                "value": val,
                                "confidence": 95,
                                "image_base64": crop,
                            }
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)
                except Exception as exc:
                    logging.error(f"[UI] OEM visual extraction failed: {exc}")
                    visual_data = extracted_data.get("visual_extractions", {})
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)

            import threading
            threading.Thread(target=oem_task, daemon=True).start()
            return

        is_disclaimer = False
        _dis_prefixes = ("dis", "dsc", "cd-")
        _dis_keywords = ("disclaimer",)
        if (doc_type == "DISCLAIMER" or
            any(fname_lower.startswith(p) for p in _dis_prefixes) or
            any(dict_fname_lower.startswith(p) for p in _dis_prefixes) or
            any(k in fname_lower for k in _dis_keywords) or
            any(k in dict_fname_lower for k in _dis_keywords)):
            is_disclaimer = True

        if is_disclaimer and os.path.exists(pdf_path):
            logging.info(f"[UI] Intercepting DISCLAIMER visual confirmations for {pdf_path}")

            loading_lbl = tk.Label(
                self.visual_frame,
                text="⏳ Extracting Disclaimer fields...\nPlease wait (approx 5-10s)",
                fg=TEXT_LIGHT_COLOR,
                bg=BG_COLOR,
                font=("Segoe UI", 10),
                justify=tk.CENTER,
            )
            loading_lbl.pack(pady=40)

            def disclaimer_task():
                try:
                    import scrappage_scheme.disclaimer_validation as dis_mod
                    disclaimer_results = dis_mod.process_disclaimer_visual(pdf_path)

                    visual_data = {}
                    for item in disclaimer_results:
                        field = item.get("field", "")
                        val   = item.get("value", "")
                        crop  = item.get("crop_b64", item.get("crop", ""))
                        if field:
                            visual_data[field] = {
                                "value": val,
                                "confidence": 95,
                                "image_base64": crop,
                            }
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)
                except Exception as exc:
                    logging.error(f"[UI] Disclaimer visual extraction failed: {exc}")
                    visual_data = extracted_data.get("visual_extractions", {})
                    self.after(0, self._render_visual_data, visual_data, loading_lbl)

            import threading
            threading.Thread(target=disclaimer_task, daemon=True).start()
            return

        visual_data = extracted_data.get("visual_extractions", {})
        self._render_visual_data(visual_data)

    def _render_visual_data(self, visual_data, loading_lbl=None):
        if loading_lbl:
            loading_lbl.destroy()
            
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
