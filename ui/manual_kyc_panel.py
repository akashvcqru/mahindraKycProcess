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

        # Visual Confirmation Viewer has been removed to maximize space for Portal Details.

        # Portal Details Viewer
        self.portal_frame = tk.LabelFrame(self.workspace_pane, text="Portal Details", bg=CARD_BG_COLOR, fg="#60A5FA", font=("Segoe UI", 10, "bold"), bd=1)
        self.workspace_pane.add(self.portal_frame, minsize=300)

        self.portal_canvas = tk.Canvas(self.portal_frame, bg="#2D2D2D", highlightthickness=0)
        port_vscroll = ttk.Scrollbar(self.portal_frame, orient="vertical", command=self.portal_canvas.yview)
        self.portal_canvas.configure(yscrollcommand=port_vscroll.set)
        
        port_vscroll.pack(side="right", fill="y")
        self.portal_canvas.pack(side="left", fill="both", expand=True, padx=2, pady=2)

        self.portal_inner = tk.Frame(self.portal_canvas, bg="#2D2D2D")
        self.portal_canvas.create_window((0, 0), window=self.portal_inner, anchor="nw")
        
        self.portal_inner.bind("<Configure>", lambda e: self.portal_canvas.configure(scrollregion=self.portal_canvas.bbox("all")))

        self.portal_canvas.bind_all("<MouseWheel>", self.on_mousewheel)

    def on_mousewheel(self, event):
        # Only scroll if manual kyc panel is mapped/visible
        if self.winfo_ismapped():
            try:
                widget = self.winfo_containing(event.x_root, event.y_root)
                if not widget:
                    return
                curr = widget
                while curr:
                    if hasattr(self, "portal_canvas") and curr == self.portal_canvas:
                        self.portal_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                        break
                    curr = curr.master
            except Exception:
                pass

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
        
        active_doc = docs[0] if docs else None
        self.load_portal_details(claim, active_doc)
        
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
            self.load_portal_details(self.selected_claim, doc)

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
        self.clear_portal_details()

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
            
        # Visual confirmations loading has been removed.

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
        self.visual_images.clear()



    def remove_current_from_queue(self):
        sel = self.history_tree.selection()
        if not sel: return
        active_item = sel[0]
        
        # Remove from treeview
        self.history_tree.delete(active_item)
        
        # Clear viewers
        self.clear_visuals()
        self.clear_portal_details()
        self.pdf_canvas.delete("all")
        self.page_label.config(text="Page 0 of 0")
        self.selected_claim = None
        self.title_label.config(text="No Row Selected")
        
        # Try to select the next item
        children = self.history_tree.get_children()
        if children:
            self.history_tree.selection_set(children[0])

    def clear_portal_details(self):
        for widget in self.portal_inner.winfo_children():
            widget.destroy()

    def load_portal_details(self, claim, active_doc=None):
        self.clear_portal_details()
        
        claim_details = claim.get("claim_details") or {}
        old_vehicle_details = claim.get("old_vehicle_details") or {}
        
        # ── Verification Issues / Mismatches Section ──
        row_issues = claim.get("issues") or []
        if row_issues:
            issues_section = tk.LabelFrame(
                self.portal_inner, text="Hold Reasons / Mismatches", bg=CARD_BG_COLOR, fg=ERROR_COLOR, font=("Segoe UI", 10, "bold"), bd=1
            )
            issues_section.pack(fill="x", padx=10, pady=5)
            
            for issue in row_issues:
                row_f = tk.Frame(issues_section, bg=CARD_BG_COLOR)
                row_f.pack(fill="x", padx=8, pady=3)
                
                # Warning label
                warn_lbl = tk.Label(row_f, text="⚠", font=("Segoe UI", 10, "bold"), fg=ERROR_COLOR, bg=CARD_BG_COLOR, anchor="nw")
                warn_lbl.pack(side="left", padx=(2, 5))
                
                issue_lbl = tk.Label(row_f, text=str(issue), font=("Segoe UI", 9, "bold"), fg="#F87171", bg=CARD_BG_COLOR, anchor="w", wraplength=210, justify="left")
                issue_lbl.pack(side="left", fill="x", expand=True)
        
        # ── Active Document Verification Rules Section ──
        if active_doc:
            validations = active_doc.get("validations") or {}
            if validations:
                doc_type = active_doc.get("file_type") or "UNKNOWN"
                doc_section = tk.LabelFrame(
                    self.portal_inner, text=f"Doc Verification: {doc_type}", bg=CARD_BG_COLOR, fg="#60A5FA", font=("Segoe UI", 10, "bold"), bd=1
                )
                doc_section.pack(fill="x", padx=10, pady=5)
                
                for rule_name, rule_res in validations.items():
                    row_f = tk.Frame(doc_section, bg=CARD_BG_COLOR)
                    row_f.pack(fill="x", padx=8, pady=2)
                    
                    res_str = str(rule_res)
                    res_upper = res_str.upper()
                    if any(k in res_upper for k in ("MATCH", "VALID", "OK", "TRUE", "PRESENT")):
                        fg_color = SUCCESS_COLOR
                    elif any(k in res_upper for k in ("MISMATCH", "INVALID", "FAILED", "FALSE", "MISSING")):
                        fg_color = ERROR_COLOR
                    else:
                        fg_color = TEXT_COLOR
                        
                    rule_lbl = tk.Label(row_f, text=f"• {rule_name}:", font=("Segoe UI", 9, "bold"), fg=TEXT_LIGHT_COLOR, bg=CARD_BG_COLOR, anchor="w")
                    rule_lbl.pack(side="left", padx=2)
                    
                    val_lbl = tk.Label(row_f, text=res_str, font=("Segoe UI", 9, "bold"), fg=fg_color, bg=CARD_BG_COLOR, anchor="w", wraplength=140, justify="left")
                    val_lbl.pack(side="left", padx=5, fill="x", expand=True)
        
        # ── Claim Details Section ──
        claim_section = tk.LabelFrame(
            self.portal_inner, text="Claim Details", bg=CARD_BG_COLOR, fg="#60A5FA", font=("Segoe UI", 10, "bold"), bd=1
        )
        claim_section.pack(fill="x", padx=10, pady=5)
        
        if claim_details:
            # We want to display these details beautifully. Let's make a grid or simple key-value layout.
            for k, v in claim_details.items():
                if not v or str(v).strip() in ("-", ""):
                    continue
                row_f = tk.Frame(claim_section, bg=CARD_BG_COLOR)
                row_f.pack(fill="x", padx=8, pady=3)
                
                k_lbl = tk.Label(row_f, text=f"{k}:", font=("Segoe UI", 9, "bold"), fg=TEXT_LIGHT_COLOR, bg=CARD_BG_COLOR, anchor="w")
                k_lbl.pack(side="left", padx=2)
                
                v_lbl = tk.Label(row_f, text=str(v), font=("Segoe UI", 9), fg=TEXT_COLOR, bg=CARD_BG_COLOR, anchor="w", wraplength=220, justify="left")
                v_lbl.pack(side="left", padx=5, fill="x", expand=True)
        else:
            tk.Label(claim_section, text="No Claim Details Available", fg=TEXT_LIGHT_COLOR, bg=CARD_BG_COLOR, font=("Segoe UI", 9, "italic")).pack(pady=10)

        # ── Old Vehicle Details Section ──
        old_veh_section = tk.LabelFrame(
            self.portal_inner, text="Old Vehicle Details", bg=CARD_BG_COLOR, fg="#60A5FA", font=("Segoe UI", 10, "bold"), bd=1
        )
        old_veh_section.pack(fill="x", padx=10, pady=5)
        
        if old_vehicle_details:
            for k, v in old_vehicle_details.items():
                if not v or str(v).strip() in ("-", ""):
                    continue
                row_f = tk.Frame(old_veh_section, bg=CARD_BG_COLOR)
                row_f.pack(fill="x", padx=8, pady=3)
                
                k_lbl = tk.Label(row_f, text=f"{k}:", font=("Segoe UI", 9, "bold"), fg=TEXT_LIGHT_COLOR, bg=CARD_BG_COLOR, anchor="w")
                k_lbl.pack(side="left", padx=2)
                
                v_lbl = tk.Label(row_f, text=str(v), font=("Segoe UI", 9), fg=TEXT_COLOR, bg=CARD_BG_COLOR, anchor="w", wraplength=220, justify="left")
                v_lbl.pack(side="left", padx=5, fill="x", expand=True)
        else:
            tk.Label(old_veh_section, text="No Old Vehicle Details Available", fg=TEXT_LIGHT_COLOR, bg=CARD_BG_COLOR, font=("Segoe UI", 9, "italic")).pack(pady=10)
