import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from controllers.tracker_controller import TrackerController

class TrackerWindow:
    def __init__(self, root):
        self.root = root
        self.controller = TrackerController()
        self.selected_db_id = None
        
        # --- Industry-Level Window Configuration ---
        self.root.title("University Lab Experiment Tracker")
        window_width, window_height = 850, 700
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int((screen_width / 2) - (window_width / 2))
        center_y = int((screen_height / 2) - (window_height / 2))
        
        self.root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        self.root.resizable(False, False)
        self.root.configure(bg="#f4f6f9")
        
        self._apply_styling()
        self._construct_ui()
        
        self._update_clock()
        self.auto_refresh()

    def _apply_styling(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        
        style.configure("Treeview", background="#ffffff", foreground="#000000", 
                        fieldbackground="#ffffff", borderwidth=1, font=("Arial", 11), rowheight=30)
        style.configure("Treeview.Heading", background="#e9ecef", foreground="#333333", 
                        font=("Arial", 11, "bold"), borderwidth=1)
        style.map('Treeview', background=[('selected', '#ffffff')], foreground=[('selected', '#000000')])

    def _construct_ui(self):
        # Top-Right Real-Time Clock
        self.lbl_clock = tk.Label(self.root, text="", bg="#f4f6f9", fg="#666666", font=("Arial", 10, "italic"))
        self.lbl_clock.pack(anchor="e", padx=20, pady=(10, 0))

        # --- Data Entry Form ---
        top_frame = tk.LabelFrame(self.root, text=" Data Entry Form ", bg="#ffffff", fg="#002147", font=("Arial", 12, "bold"), pady=15, padx=15)
        top_frame.pack(fill="x", padx=20, pady=(5, 15))

        tk.Label(top_frame, text="Experiment Title:", bg="#ffffff", fg="#333333", font=("Arial", 11, "bold")).grid(row=0, column=0, padx=5, pady=8, sticky="e")
        self.entry_title = tk.Entry(top_frame, width=32, font=("Arial", 11), relief="solid", borderwidth=1, bg="#fafafa")
        self.entry_title.grid(row=0, column=1, padx=5, ipady=3)

        tk.Label(top_frame, text="Student ID:", bg="#ffffff", fg="#333333", font=("Arial", 11, "bold")).grid(row=0, column=2, padx=15, sticky="e")
        self.entry_student = tk.Entry(top_frame, width=18, font=("Arial", 11), relief="solid", borderwidth=1, bg="#fafafa")
        self.entry_student.grid(row=0, column=3, padx=5, ipady=3)

        tk.Label(top_frame, text="Current Status:", bg="#ffffff", fg="#333333", font=("Arial", 11, "bold")).grid(row=1, column=0, pady=10, sticky="e")
        self.combo_status = ttk.Combobox(top_frame, values=["Pending", "In Progress", "Completed"], state="readonly", width=30, font=("Arial", 11))
        self.combo_status.current(0)
        self.combo_status.grid(row=1, column=1, padx=5, ipady=3)

        self.btn_save = tk.Button(top_frame, text="SAVE RECORD", command=self.add_experiment, bg="#198754", fg="white", font=("Arial", 10, "bold"), relief="flat", padx=15, pady=4, cursor="hand2")
        self.btn_save.grid(row=1, column=2, columnspan=2, sticky="ew", padx=15)

        # Real-Time Warning Label
        self.lbl_warning = tk.Label(top_frame, text="", bg="#ffffff", fg="#dc3545", font=("Arial", 10, "bold"))
        self.lbl_warning.grid(row=2, column=0, columnspan=4, pady=5)

        # Triggers the check instantly every time you release a key on the title field
        self.entry_title.bind("<KeyRelease>", self._realtime_duplicate_check)

        # --- Data Grid (Treeview) ---
        mid_frame = tk.Frame(self.root, bg="#ffffff", relief="solid", borderwidth=1)
        mid_frame.pack(fill="both", expand=True, padx=20, pady=5)

        scroller = tk.Scrollbar(mid_frame, orient="vertical")
        self.tree = ttk.Treeview(mid_frame, columns=("c0", "c1", "c2", "c3", "c4"), show="headings", yscrollcommand=scroller.set)
        scroller.config(command=self.tree.yview)
        scroller.pack(side="right", fill="y")
        
        safe_columns = ("c0", "c1", "c2", "c3", "c4")
        headers = ["SELECT", "ID", "EXPERIMENT TITLE", "STUDENT ID", "STATUS"]
        widths = [70, 50, 300, 150, 150]
        
        for col, head, w in zip(safe_columns, headers, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor="center")
        
        # Surrounding Box Highlights
        self.tree.tag_configure("Pending", background="#cce5ff", foreground="#000000")
        self.tree.tag_configure("In Progress", background="#ffe5b4", foreground="#000000")
        self.tree.tag_configure("Completed", background="#d4edda", foreground="#000000")
        self.tree.tag_configure("Selected", background="#002147", foreground="#ffffff")
        
        self.tree.bind("<ButtonRelease-1>", self._on_row_click)
        self.tree.pack(fill="both", expand=True)

        # --- Update & Delete Commands ---
        btm_frame = tk.LabelFrame(self.root, text=" Modify Selected Record ", bg="#ffffff", fg="#002147", font=("Arial", 12, "bold"), pady=15, padx=15)
        btm_frame.pack(fill="x", padx=20, pady=15)

        tk.Label(btm_frame, text="Change Status To:", bg="#ffffff", fg="#333333", font=("Arial", 11, "bold")).grid(row=0, column=0, padx=5, pady=10)
        self.combo_update = ttk.Combobox(btm_frame, values=["Pending", "In Progress", "Completed"], state="readonly", width=22, font=("Arial", 11))
        self.combo_update.current(0)
        self.combo_update.grid(row=0, column=1, padx=15, ipady=3)

        tk.Button(btm_frame, text="UPDATE RECORD", command=self.update_status, bg="#0d6efd", fg="white", font=("Arial", 10, "bold"), relief="flat", padx=15, pady=4, cursor="hand2").grid(row=0, column=2, padx=15)
        tk.Button(btm_frame, text="DELETE RECORD", command=self.delete_selected, bg="#dc3545", fg="white", font=("Arial", 10, "bold"), relief="flat", padx=15, pady=4, cursor="hand2").grid(row=0, column=3, padx=15)

    # ==========================================
    # 3. INTERACTION & REAL-TIME LOGIC
    # ==========================================
    def _update_clock(self):
        current_time = datetime.now().strftime("%B %d, %Y  |  %I:%M:%S %p")
        self.lbl_clock.config(text=current_time)
        self.root.after(1000, self._update_clock)

    def _realtime_duplicate_check(self, event=None):
        """Fires instantly when typing OR when the database undergoes changes."""
        t = self.entry_title.get().strip()
        
        # Check DB instantly for duplicate titles
        if t and self.controller.check_duplicate_title(t):
            self.entry_title.config(bg="#f8d7da") # Turn box light red
            self.btn_save.config(state="disabled", bg="#6c757d")
            self.lbl_warning.config(text=f"⚠️ Title '{t}' already exists.")
        else:
            self.entry_title.config(bg="#fafafa") # Back to white
            self.btn_save.config(state="normal", bg="#198754")
            self.lbl_warning.config(text="")

    def _on_row_click(self, event):
        item = self.tree.focus()
        if not item: return
            
        values = self.tree.item(item, "values")
        if values:
            clicked_id = int(values[1])
            if self.selected_db_id == clicked_id:
                self.selected_db_id = None 
            else:
                self.selected_db_id = clicked_id
            self.load_data()

    def load_data(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        rows = self.controller.fetch_all_experiments()
        for data in rows:
            db_id = data[0]
            title = data[1]
            student_id = data[2]
            status = data[3]
            
            if self.selected_db_id == db_id:
                tick = "☑"
                tag = "Selected"
            else:
                tick = "☐"
                tag = status
                
            self.tree.insert("", "end", values=(tick, db_id, title, student_id, status), tags=(tag,))
            
        # Instantly re-evaluates the form's duplicate check when data changes
        self._realtime_duplicate_check()

    def add_experiment(self):
        title = self.entry_title.get().strip()
        student_id = self.entry_student.get().strip()
        status = self.combo_status.get()
        
        success, msg = self.controller.add_experiment(title, student_id, status)
        if success:
            self.entry_title.delete(0, tk.END)
            self.entry_student.delete(0, tk.END)
            self.selected_db_id = None
            self.load_data()
        else:
            messagebox.showerror("Data Error", msg)

    def update_status(self):
        if not self.selected_db_id:
            messagebox.showwarning("No Selection", "Please tick the box next to the record you wish to update.")
            return
            
        new_status = self.combo_update.get()
        success, msg = self.controller.update_status(self.selected_db_id, new_status)
        if success:
            self.selected_db_id = None
            self.load_data()
        else:
            messagebox.showerror("Error", msg)

    def delete_selected(self):
        if not self.selected_db_id:
            messagebox.showwarning("No Selection", "Please tick the box next to the record you wish to delete.")
            return
            
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete Experiment ID {self.selected_db_id}?")
        if not confirm:
            return
            
        success, msg = self.controller.delete_experiment(self.selected_db_id)
        if success:
            self.selected_db_id = None
            
            # Since load_data() includes _realtime_duplicate_check(), the UI will unlock 
            # the text box immediately after the deletion occurs!
            self.load_data()
        else:
            messagebox.showerror("Error", msg)

    def auto_refresh(self):
        self.load_data()
        self.root.after(2000, self.auto_refresh)