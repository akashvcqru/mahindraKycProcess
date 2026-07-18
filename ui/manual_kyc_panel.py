import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import fitz
import os
import base64
import io
import logging
import threading

BG_COLOR = "#1E1E1E"
CARD_BG_COLOR = "#121212"
TEXT_COLOR = "#E0E0E0"
TEXT_LIGHT_COLOR = "#A0A0A0"
ACCENT_COLOR = "#2563EB"
SUCCESS_COLOR = "#10B981"
WARNING_COLOR = "#F59E0B"
ERROR_COLOR = "#EF4444"

class ManualKycPanel(tk.Frame):
    def __init__(self, master, app_ref):
        super().__init__(master, bg=BG_COLOR)
        self.app_ref = app_ref  # Reference to AppUI
        self.processed_claims = []
        self.current_pdf_doc = None
        self.current_pdf_page = 0
        self.current_zoom = 1.0
        self.canvas_photo = None
        self.visual_images = []
        self.selected_claim = None
        self.current_pdf_path = None

        self.setup_ui()

    def setup_ui(self):
        self.split_pane = tk.PanedWindow(self, orient="horizontal", bg=BG_COLOR, bd=0, sashwidth=6, sashrelief="flat")
        self.split_pane.pack(fill="both", expand=True)

        # 1. Left Queue list for HOLD cases
        self.list_frame = tk.LabelFrame(
            self.split_pane, text="Manual Review Queue (HOLD)", bg=CARD_BG_COLOR, fg="#60A5FA", font=("Segoe UI", 10, "bold"), bd=1, width=280
        )
        self.list_frame.pack_propagate(False)
        self.split_pane.add(self.list_frame, minsize=280)

        self.history_tree = ttk.Treeview(self.list_frame, columns=("Row", "Customer"), show="headings", selectmode="browse")
        self.history_tree.heading("Row", text="Idx")
        self.history_tree.heading("Customer", text="Customer Name")
        self.history_tree.column("Row", width=50, anchor="center")
        self.history_tree.column("Customer", width=180, anchor="w")
        self.history_tree.tag_configure("hold", foreground=WARNING_COLOR, font=("Segoe UI", 9, "bold"))
        self.history_tree.bind("<<TreeviewSelect>>", self.on_select_item)

        tree_scroll = ttk.Scrollbar(self.list_frame, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=tree_scroll.set)
        self.history_tree.pack(fill="both", expand=True, side="left", padx=5, pady=5)
        tree_scroll.pack(fill="y", side="right")

        # 2. Right Workspace Panel Container (parent of Action Header and Workspace Pane)
        self.right_container = tk.Frame(self.split_pane, bg=BG_COLOR)
        self.split_pane.add(self.right_container)

        # Action Header (Approve, Hold, Reject Buttons)
        self.action_header = tk.Frame(self.right_container, bg=CARD_BG_COLOR, bd=1, relief="solid", height=50)
        self.action_header.pack(fill="x", side="top", padx=5, pady=(5, 0))
        self.action_header.pack_propagate(False)

        self.title_label = tk.Label(
            self.action_header,
            text="No Row Selected",
            bg=CARD_BG_COLOR,
            fg="#60A5FA",
            font=("Segoe UI", 10, "bold")
        )
        self.title_label.pack(side="left", padx=15, pady=10)

        self.workspace_pane = tk.PanedWindow(self.right_container, orient="horizontal", bg=BG_COLOR, bd=0, sashwidth=6, sashrelief="flat")
        self.workspace_pane.pack(fill="both", expand=True, padx=5, pady=5)

        # Document Viewer
        self.doc_frame = tk.LabelFrame(self.workspace_pane, text="Document Viewer", bg=CARD_BG_COLOR, fg="#60A5FA", font=("Segoe UI", 10, "bold"), bd=1)
        self.workspace_pane.add(self.doc_frame, minsize=400)

        doc_controls = tk.Frame(self.doc_frame, bg=CARD_BG_COLOR)
        doc_controls.pack(fill="x", padx=5, pady=5)

        self.doc_selector_var = tk.StringVar()
        self.doc_selector = ttk.Combobox(doc_controls, textvariable=self.doc_selector_var, state="readonly", width=25)
        self.doc_selector.pack(side="left", padx=5)
        self.doc_selector.bind("<<ComboboxSelected>>", self.on_doc_change)

        btn_prev = tk.Button(doc_controls, text="◀", bg="#333", fg="white", bd=0, padx=6, command=self.page_prev)
        btn_prev.pack(side="left", padx=2)
        self.page_label = tk.Label(doc_controls, text="Page 0 of 0", bg=CARD_BG_COLOR, fg=TEXT_COLOR)
        self.page_label.pack(side="left", padx=5)
        btn_next = tk.Button(doc_controls, text="▶", bg="#333", fg="white", bd=0, padx=6, command=self.page_next)
        btn_next.pack(side="left", padx=2)

        btn_zoom_out = tk.Button(doc_controls, text="🔍-", bg="#333", fg="white", bd=0, padx=6, command=self.zoom_out)
        btn_zoom_out.pack(side="right", padx=2)
        self.zoom_label = tk.Label(doc_controls, text="100%", bg=CARD_BG_COLOR, fg=TEXT_COLOR)
        self.zoom_label.pack(side="right", padx=5)
        btn_zoom_in = tk.Button(doc_controls, text="🔍+", bg="#333", fg="white", bd=0, padx=6, command=self.zoom_in)
        btn_zoom_in.pack(side="right", padx=2)

        self.pdf_canvas = tk.Canvas(self.doc_frame, bg="#2D2D2D", highlightthickness=0)
        pdf_vscroll = ttk.Scrollbar(self.doc_frame, orient="vertical", command=self.pdf_canvas.yview)
        pdf_hscroll = ttk.Scrollbar(self.doc_frame, orient="horizontal", command=self.pdf_canvas.xview)
        self.pdf_canvas.configure(yscrollcommand=pdf_vscroll.set, xscrollcommand=pdf_hscroll.set)

        pdf_vscroll.pack(side="right", fill="y")
        pdf_hscroll.pack(side="bottom", fill="x")
        self.pdf_canvas.pack(fill="both", expand=True, padx=2, pady=2)

        # Drag-to-pan mouse bindings
        self.pdf_canvas.bind("<Button-1>", self.start_pan)
        self.pdf_canvas.bind("<B1-Motion>", self.drag_pan)
        # Mousewheel zoom & scroll bindings
        self.pdf_canvas.bind("<MouseWheel>", self.on_pdf_mousewheel)

        # Visual Confirmation Viewer
        self.visual_frame = tk.LabelFrame(self.workspace_pane, text="Visual Confirmation Crops", bg=CARD_BG_COLOR, fg="#60A5FA", font=("Segoe UI", 10, "bold"), bd=1)
        self.workspace_pane.add(self.visual_frame, minsize=350)

        self.visual_canvas = tk.Canvas(self.visual_frame, bg="#2D2D2D", highlightthickness=0)
        vis_vscroll = ttk.Scrollbar(self.visual_frame, orient="vertical", command=self.visual_canvas.yview)
        self.visual_canvas.configure(yscrollcommand=vis_vscroll.set)
        
        vis_vscroll.pack(side="right", fill="y")
        self.visual_canvas.pack(side="left", fill="both", expand=True, padx=2, pady=2)

        self.visual_inner = tk.Frame(self.visual_canvas, bg="#2D2D2D")
        self.visual_canvas.create_window((0, 0), window=self.visual_inner, anchor="nw")
        
        # Configure mousewheel and scroll bindings
        self.visual_inner.bind("<Configure>", lambda e: self.visual_canvas.configure(scrollregion=self.visual_canvas.bbox("all")))
        self.visual_canvas.bind_all("<MouseWheel>", self.on_mousewheel)

    def on_mousewheel(self, event):
        # Only scroll if mouse is over manual kyc visual panel
        if self.winfo_ismapped() and self.visual_canvas.winfo_exists():
            self.visual_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def start_pan(self, event):
        self.pdf_canvas.scan_mark(event.x, event.y)

    def drag_pan(self, event):
        self.pdf_canvas.scan_dragto(event.x, event.y, gain=1)

    def on_pdf_mousewheel(self, event):
        try:
            is_control = (event.state & 4) != 0
            is_shift = (event.state & 1) != 0
            
            if is_control:
                # Zoom in / out
                if event.delta > 0:
                    self.zoom_in()
                elif event.delta < 0:
                    self.zoom_out()
            elif is_shift:
                # Horizontal scroll
                self.pdf_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                # Vertical scroll
                self.pdf_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def add_row(self, row_result):
        self.processed_claims.append(row_result)
        idx = len(self.processed_claims) - 1
        if row_result.get("status") == "HOLD":
            self.history_tree.insert(
                "", "end",
                iid=str(idx),
                values=(f"Row {row_result['row_idx'] + 1}", row_result.get("customer_name", "Unknown")),
                tags=("hold",)
            )

    def on_select_item(self, event):
        sel = self.history_tree.selection()
        if not sel: return
        item_id = sel[0]
        try:
            idx = int(item_id)
            claim = self.processed_claims[idx]
            self.load_claim(claim)
        except Exception as e:
            logging.error(f"Error selecting manual kyc item: {e}")

    def load_claim(self, claim):
        self.selected_claim = claim
        self.title_label.config(text=f"Reviewing: Row {claim.get('row_idx') + 1} - {claim.get('customer_name')}")
        self.app_ref.selected_claim = claim
        self.app_ref.update_header_toggles()
        
        docs = claim.get("documents", [])
        names = [d.get("file_name") for d in docs]
        self.doc_selector.configure(values=names)
        if names:
            self.doc_selector.set(names[0])
            self.load_pdf(docs[0])
        else:
            self.doc_selector.set("No Documents")
            self.pdf_canvas.delete("all")
            self.page_label.config(text="Page 0 of 0")
            self.clear_visuals()

    def on_doc_change(self, event):
        if not self.selected_claim: return
        name = self.doc_selector_var.get()
        doc = next((d for d in self.selected_claim.get("documents", []) if d.get("file_name") == name), None)
        if doc:
            self.load_pdf(doc)

    def clear_queue(self):
        self.processed_claims = []
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        self.selected_claim = None
        self.title_label.config(text="No Row Selected")
        self.doc_selector.configure(values=[])
        self.doc_selector.set("")
        self.pdf_canvas.delete("all")
        self.page_label.config(text="Page 0 of 0")
        self.clear_visuals()

    def load_pdf(self, doc_dict):
        path = doc_dict.get("file_path")
        self.current_pdf_path = path
        
        if doc_dict.get("is_url"):
            self.current_pdf_doc = None
            self.current_pdf_page = 0
            self.current_zoom = 1.0
            self.pdf_canvas.delete("all")
            self.page_label.config(text="Downloading Image...")

            def download_task():
                try:
                    url = doc_dict.get("file_path")
                    direct_url = url
                    if "drive.google.com" in url:
                        import re
                        match = re.search(r"/d/([^/]+)", url)
                        if match:
                            direct_url = f"https://drive.google.com/uc?export=download&id={match.group(1)}"
                    
                    import requests
                    import io
                    resp = requests.get(direct_url, timeout=20)
                    if resp.status_code == 200:
                        img = Image.open(io.BytesIO(resp.content))
                        self.current_image_original = img
                        self.after(0, self.display_downloaded_image)
                    else:
                        self.after(0, lambda: self.page_label.config(text="Download Failed"))
                except Exception as e:
                    logging.error(f"Error downloading stitched image in manual panel: {e}")
                    self.after(0, lambda: self.page_label.config(text="Download Error"))

            threading.Thread(target=download_task, daemon=True).start()
            self.clear_visuals()
            return

        if path and os.path.exists(path):
            try:
                if self.current_pdf_doc:
                    self.current_pdf_doc.close()
                self.current_pdf_doc = fitz.open(path)
                self.current_pdf_page = 0
                self.current_zoom = 1.1
                self.render_pdf_page()
            except Exception as e:
                logging.error(f"Error opening PDF: {e}")
                self.pdf_canvas.delete("all")
                self.page_label.config(text="Error")
        else:
            self.pdf_canvas.delete("all")
            self.page_label.config(text="Not Found")
            
        # Async load the visual confirmations for this selected document dict
        self.load_visual_confirmations(doc_dict)

    def display_downloaded_image(self):
        if not hasattr(self, "current_image_original") or not self.current_image_original:
            return
        try:
            w, h = self.current_image_original.size
            new_w = int(w * self.current_zoom)
            new_h = int(h * self.current_zoom)
            resized = self.current_image_original.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            self.canvas_photo = ImageTk.PhotoImage(resized)
            self.pdf_canvas.delete("all")
            self.pdf_canvas.create_image(0, 0, anchor="nw", image=self.canvas_photo)
            self.pdf_canvas.configure(scrollregion=(0, 0, new_w, new_h))
            self.page_label.config(text="Stitched Image (1 of 1)")
            self.zoom_label.config(text=f"{int(self.current_zoom * 100)}%")
        except Exception as e:
            logging.error(f"Error displaying downloaded image in manual panel: {e}")

    def render_pdf_page(self):
        if not self.current_pdf_doc: return
        try:
            page = self.current_pdf_doc.load_page(self.current_pdf_page)
            mat = fitz.Matrix(self.current_zoom, self.current_zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.canvas_photo = ImageTk.PhotoImage(img)

            self.pdf_canvas.delete("all")
            self.pdf_canvas.create_image(0, 0, image=self.canvas_photo, anchor="nw")
            self.pdf_canvas.configure(scrollregion=self.pdf_canvas.bbox("all"))

            total = len(self.current_pdf_doc)
            self.page_label.config(text=f"Page {self.current_pdf_page + 1} of {total}")
            self.zoom_label.config(text=f"{int(self.current_zoom * 100)}%")
        except Exception as e:
            logging.error(f"Error rendering PDF: {e}")

    def page_prev(self):
        if self.current_pdf_doc and self.current_pdf_page > 0:
            self.current_pdf_page -= 1
            self.render_pdf_page()

    def page_next(self):
        if self.current_pdf_doc and self.current_pdf_page < len(self.current_pdf_doc) - 1:
            self.current_pdf_page += 1
            self.render_pdf_page()

    def zoom_in(self):
        if self.current_zoom < 3.0:
            self.current_zoom += 0.15
            if self.current_pdf_doc:
                self.render_pdf_page()
            elif hasattr(self, "current_image_original") and self.current_image_original:
                self.display_downloaded_image()

    def zoom_out(self):
        if self.current_zoom > 0.4:
            self.current_zoom -= 0.15
            if self.current_pdf_doc:
                self.render_pdf_page()
            elif hasattr(self, "current_image_original") and self.current_image_original:
                self.display_downloaded_image()

    def clear_visuals(self):
        for widget in self.visual_inner.winfo_children():
            widget.destroy()
        self.visual_images.clear()

    # --- Live on-the-fly extraction of Visual Crops, exactly mirroring AppUI ---
    def load_visual_confirmations(self, doc_dict):
        self.clear_visuals()
        
        extracted_data = doc_dict.get("extracted_data", {})
        pdf_path = doc_dict.get("file_path", doc_dict.get("path", ""))
        doc_type = doc_dict.get("file_type", doc_dict.get("doc_type", "")).upper()
        
        is_ledger = False
        fname_lower = os.path.basename(pdf_path).lower() if pdf_path else ""
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

        is_cod = False
        _cod_prefixes = ("cod",)
        _cod_keywords = ("certificate of deposit", "cod")
        if (doc_type == "COD" or
            any(fname_lower.startswith(p) for p in _cod_prefixes) or
            any(dict_fname_lower.startswith(p) for p in _cod_prefixes) or
            any(k in fname_lower for k in _cod_keywords) or
            any(k in dict_fname_lower for k in _cod_keywords)):
            is_cod = True

        is_oem = False
        _oem_prefixes = ("oem",)
        _oem_keywords = ("scrappage certificate", "oem")
        if (doc_type == "OEM" or
            any(fname_lower.startswith(p) for p in _oem_prefixes) or
            any(dict_fname_lower.startswith(p) for p in _oem_prefixes) or
            any(k in fname_lower for k in _oem_keywords) or
            any(k in dict_fname_lower for k in _oem_keywords)):
            is_oem = True

        is_disclaimer = False
        _dis_prefixes = ("dis", "dsc", "cd-")
        _dis_keywords = ("disclaimer",)
        if (doc_type == "DISCLAIMER" or
            any(fname_lower.startswith(p) for p in _dis_prefixes) or
            any(dict_fname_lower.startswith(p) for p in _dis_prefixes) or
            any(k in fname_lower for k in _dis_keywords) or
            any(k in dict_fname_lower for k in _dis_keywords)):
            is_disclaimer = True

        # Render loading status
        loading_lbl = tk.Label(
            self.visual_inner,
            text="⏳ Extracting verification crops...\nPlease wait...",
            fg=TEXT_LIGHT_COLOR, bg="#2D2D2D",
            font=("Segoe UI", 10), justify=tk.CENTER
        )
        loading_lbl.pack(pady=40)

        # Worker tasks
        def task():
            try:
                visual_data = {}
                scheme_type = self.app_ref.scheme_type_var.get()
                
                if is_ledger and os.path.exists(pdf_path):
                    if scheme_type == "Scrappage Bonus Scheme":
                        import scrappage_scheme.ledger_validation as scrappage_ledger
                        results = scrappage_ledger.process_scrappage_ledger_visual(pdf_path)
                    else:
                        import welcome_scheme.ledger_validation as welcome_ledger
                        results = welcome_ledger.process_east_welcome_bonus_ledger(pdf_path)
                elif is_invoice and os.path.exists(pdf_path):
                    if scheme_type == "Scrappage Bonus Scheme":
                        import scrappage_scheme.invoice_validation as inv_mod
                        results = inv_mod.process_invoice_visual(pdf_path)
                    else:
                        import welcome_scheme.invoice_validation as welcome_inv
                        results = welcome_inv.process_invoice_visual(pdf_path)
                elif is_cod and os.path.exists(pdf_path):
                    import scrappage_scheme.cod_validation as cod_mod
                    results = cod_mod.process_cod_visual(pdf_path)
                elif is_oem and os.path.exists(pdf_path):
                    import scrappage_scheme.oem_document_validation as oem_mod
                    c_details = self.selected_claim.get("claim_details") or {}
                    v_details = self.selected_claim.get("old_vehicle_details") or {}
                    results = oem_mod.process_oem_visual(
                        pdf_path,
                        old_chassis=v_details.get("Chassis No", "").strip(),
                        old_reg=v_details.get("Reg. No", v_details.get("Reg No", "")).strip() or c_details.get("Reg. No", "").strip(),
                        new_chassis=c_details.get("Chassis No", "").strip()
                    )
                elif is_disclaimer and os.path.exists(pdf_path):
                    if scheme_type == "Scrappage Bonus Scheme":
                        import scrappage_scheme.disclaimer_validation as dis_mod
                        results = dis_mod.process_disclaimer_visual(pdf_path)
                    else:
                        import welcome_scheme.disclaimer_validation as welcome_disclaimer
                        results = welcome_disclaimer.process_disclaimer_visual(pdf_path)
                else:
                    results = []

                for item in results:
                    f = item.get("field", "")
                    if f:
                        visual_data[f] = {
                            "value": item.get("value", ""),
                            "confidence": 95,
                            "image_base64": item.get("crop_b64", item.get("crop", ""))
                        }
                        
                # Fallback to already parsed extractions
                if not visual_data:
                    visual_data = extracted_data.get("visual_extractions", {})
                
                self.after(0, self._render_visual_cards, visual_data, loading_lbl)
            except Exception as e:
                logging.error(f"[Manual KYC Panel] Visual extraction thread failed: {e}")
                fallback_data = extracted_data.get("visual_extractions", {})
                self.after(0, self._render_visual_cards, fallback_data, loading_lbl)

        threading.Thread(target=task, daemon=True).start()

    def _render_visual_cards(self, visual_data, loading_lbl):
        if loading_lbl:
            loading_lbl.destroy()

        if not visual_data:
            tk.Label(self.visual_inner, text="👁️ No visual crop data available.", fg=TEXT_LIGHT_COLOR, bg="#2D2D2D", font=("Segoe UI", 10)).pack(pady=40)
            return

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

        for field_name, extraction in visual_data.items():
            card = tk.Frame(self.visual_inner, bg=CARD_BG_COLOR, bd=1, relief="solid")
            card.pack(fill="x", padx=10, pady=5)

            # Header
            header = tk.Frame(card, bg="#2A2A2A")
            header.pack(fill="x")
            
            title = emoji_map.get(field_name, field_name.replace("_", " ").title())
            tk.Label(header, text=title, font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg="#2A2A2A").pack(side="left", padx=10, pady=6)

            confidence = extraction.get("confidence", 0)
            badge_color = SUCCESS_COLOR if confidence >= 80 else (WARNING_COLOR if confidence >= 60 else ERROR_COLOR)
            tk.Label(header, text=f"{confidence}%", font=("Segoe UI", 9, "bold"), fg=badge_color, bg="#2A2A2A").pack(side="right", padx=10, pady=6)

            # Body
            body = tk.Frame(card, bg=CARD_BG_COLOR)
            body.pack(fill="both", expand=True, padx=10, pady=10)

            img_b64 = extraction.get("image_base64")
            if img_b64:
                try:
                    img_bytes = base64.b64decode(img_b64)
                    img = Image.open(io.BytesIO(img_bytes))
                    
                    # Resize thumbnail
                    img.thumbnail((320, 160), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.visual_images.append(photo)

                    tk.Label(body, image=photo, bg=CARD_BG_COLOR).pack(pady=(0, 8))
                except Exception as e:
                    tk.Label(body, text="⚠️ Image decode error", fg=ERROR_COLOR, bg=CARD_BG_COLOR, font=("Segoe UI", 8)).pack()
            else:
                tk.Label(body, text="⚠️ No image data", fg=WARNING_COLOR, bg=CARD_BG_COLOR).pack()

            # Extracted Value Label
            val_txt = extraction.get("value", "")
            tk.Label(body, text=f"Extracted: {val_txt}", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=CARD_BG_COLOR).pack(anchor="w")



    def remove_current_from_queue(self):
        sel = self.history_tree.selection()
        if not sel: return
        active_item = sel[0]
        
        # Remove from treeview
        self.history_tree.delete(active_item)
        
        # Clear viewers
        self.clear_visuals()
        self.pdf_canvas.delete("all")
        self.page_label.config(text="Page 0 of 0")
        self.selected_claim = None
        self.title_label.config(text="No Row Selected")
        
        # Try to select the next item
        children = self.history_tree.get_children()
        if children:
            self.history_tree.selection_set(children[0])
