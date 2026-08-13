import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
import bcrypt
import logging
import os
import csv
import time
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ValidationError
import re

# ==========================================
# 1. CENTRAL LOGGING SYSTEM
# ==========================================
def setup_logger():
    log_dir = "app_logging"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logging.basicConfig(
        filename=os.path.join(log_dir, "app.log"),
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    return logging.getLogger("HardwareAuthApp")

logger = setup_logger()

# ==========================================
# 2. MODELS & SCHEMAS (Pydantic Validation)
# ==========================================
class UserSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    email: str = Field(...)
    password: str = Field(...)
    
    @field_validator('username')
    def username_alphanumeric(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError('Username must be alphanumeric.')
        return v

    @field_validator('email')
    def validate_email(cls, v):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError('Invalid email format.')
        return v

    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long.')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must have at least one uppercase letter.')
        if not re.search(r"[0-9]", v):
            raise ValueError('Password must have at least one number.')
        if not re.search(r"[@#$%^&*]", v):
            raise ValueError('Password must have at least one special character (@#$%^&*).')
        return v

class HardwareSchema(BaseModel):
    item_name: str = Field(..., min_length=2)
    category: str = Field(..., min_length=2)
    quantity: int = Field(..., ge=0)
    unit_price: float = Field(..., ge=0.0)

def init_db(db_name="hardware_inventory.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hardware (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# ==========================================
# 3. CONTROLLERS
# ==========================================
class AuthController:
    def __init__(self, db_name="hardware_inventory.db"):
        self.db_name = db_name
        self.login_attempts = {} 

    def register(self, username, email, password):
        try:
            validated = UserSchema(username=username, email=email, password=password)
        except ValidationError as e:
            msg = e.errors()[0]['msg']
            logger.warning(f"Registration validation failed: {msg}")
            return False, f"Validation Error: {msg}"
            
        hashed_pw = bcrypt.hashpw(validated.password.encode('utf-8'), bcrypt.gensalt())
        try:
            # FIX APPLIED HERE: Added timeout=15 to prevent "database is locked" crashes
            conn = sqlite3.connect(self.db_name, timeout=15)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", 
                           (validated.username, validated.email, hashed_pw.decode('utf-8')))
            conn.commit()
            conn.close()
            logger.info(f"Account registered: '{validated.username}'")
            return True, "Registration successful! You may now log in."
        except sqlite3.IntegrityError as e:
            if "email" in str(e).lower():
                logger.warning(f"Failed registration: Email '{email}' taken.")
                return False, "Email already registered."
            logger.warning(f"Failed registration: Username '{username}' taken.")
            return False, "Username already taken."
        except sqlite3.OperationalError as e:
            logger.error(f"Database lock error during registration: {e}")
            return False, "System busy. Please try registering again in a few moments."

    def login(self, username, password):
        if not username or not password:
            return False, "Please enter both fields.", 0

        record = self.login_attempts.get(username, {'count': 0, 'lock_time': 0})
        current_time = time.time()
        
        if record['lock_time'] > current_time:
            wait_time = int(record['lock_time'] - current_time)
            return False, f"Account locked. Try again in {wait_time} seconds.", wait_time
            
        try:
            conn = sqlite3.connect(self.db_name, timeout=15)
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            conn.close()
        except sqlite3.OperationalError:
            return False, "Database is currently busy. Please try again.", 0
        
        if row and bcrypt.checkpw(password.encode('utf-8'), row[0].encode('utf-8')):
            if username in self.login_attempts:
                del self.login_attempts[username]
            logger.info(f"Auth Success: User '{username}' logged in.")
            return True, "Login successful!", 0
        else:
            record['count'] += 1
            if record['count'] >= 3:
                record['lock_time'] = current_time + 30 
                record['count'] = 0
                self.login_attempts[username] = record
                logger.warning(f"Account '{username}' locked out for 30 seconds.")
                return False, "Too many failed attempts. Account locked for 30 seconds.", 30
            else:
                self.login_attempts[username] = record
                logger.warning(f"Auth Failed: Invalid attempt for '{username}'.")
                return False, f"Invalid username or password. Attempts left: {3 - record['count']}", 0

class InventoryController:
    def __init__(self, db_name="hardware_inventory.db"):
        self.db_name = db_name

    def check_duplicate(self, item_name):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM hardware WHERE LOWER(item_name) = LOWER(?)", (item_name,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def compute_status(self, qty):
        if qty > 5: return "In Stock"
        elif 1 <= qty <= 5: return "Low Stock"
        else: return "Out of Stock"

    def fetch_all(self):
        conn = sqlite3.connect(self.db_name)
        data = conn.execute("SELECT * FROM hardware").fetchall()
        conn.close()
        return data

    def get_total_valuation(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(quantity * unit_price) FROM hardware")
        total = cursor.fetchone()[0]
        conn.close()
        return total if total else 0.0

    def add_item(self, name, category, qty_str, price_str):
        if self.check_duplicate(name):
            return False, "Item name already exists."
        try:
            qty = int(qty_str)
            price = float(price_str)
            validated = HardwareSchema(item_name=name, category=category, quantity=qty, unit_price=price)
        except ValueError:
            logger.warning("Validation failed: Non-numeric quantity/price entered.")
            return False, "Quantity must be an integer, Price must be a number."
        except ValidationError as e:
            msg = e.errors()[0]['msg']
            logger.warning(f"Validation failed: {msg}")
            return False, f"Validation Error: {msg}"

        status = self.compute_status(validated.quantity)
        conn = sqlite3.connect(self.db_name)
        conn.execute("INSERT INTO hardware (item_name, category, quantity, unit_price, status) VALUES (?, ?, ?, ?, ?)", 
                     (validated.item_name, validated.category, validated.quantity, validated.unit_price, status))
        conn.commit()
        conn.close()
        logger.info(f"Item added: {validated.item_name}")
        return True, "Success"

    def update_item(self, item_id, new_qty_str, new_price_str):
        try:
            new_qty = int(new_qty_str)
            new_price = float(new_price_str)
            if new_qty < 0 or new_price < 0: raise ValueError
        except ValueError:
            logger.warning("Validation failed: Invalid update values.")
            return False, "Values must be valid positive numbers."

        new_status = self.compute_status(new_qty)
        conn = sqlite3.connect(self.db_name)
        conn.execute("UPDATE hardware SET quantity = ?, unit_price = ?, status = ? WHERE item_id = ?", 
                     (new_qty, new_price, new_status, item_id))
        conn.commit()
        conn.close()
        logger.info(f"Item ID {item_id} updated.")
        return True, "Success"

    def delete_item(self, item_id):
        conn = sqlite3.connect(self.db_name)
        conn.execute("DELETE FROM hardware WHERE item_id = ?", (item_id,))
        conn.commit()
        conn.close()
        logger.info(f"Item ID {item_id} deleted.")

    def export_csv(self):
        try:
            conn = sqlite3.connect(self.db_name)
            rows = conn.execute("SELECT * FROM hardware").fetchall()
            conn.close()
            with open("inventory_report.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Item Name", "Category", "Quantity", "Unit Price", "Status"])
                writer.writerows(rows)
            logger.info("Report Generation Event: inventory_report.csv exported.")
            return True, "Report successfully exported to inventory_report.csv"
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False, "Export failed."

# ==========================================
# 4. VIEWS (Login, Register & Dashboard)
# ==========================================
class HardwareApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.auth_ctrl = AuthController()
        self.inv_ctrl = InventoryController()
        
        self.title("Campus Hardware System")
        self.resizable(False, False)
        self.configure(bg="#f4f6f9")
        
        self.current_user = None
        self.selected_db_id = None
        self.refresh_job = None
        
        self.show_login_screen()

    def center_window(self, w, h):
        sx, sy = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{int((sx/2)-(w/2))}+{int((sy/2)-(h/2))}")

    def clear_window(self):
        if self.refresh_job:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None
        for widget in self.winfo_children():
            widget.destroy()

    # --- 4A. LOGIN SCREEN ---
    def show_login_screen(self):
        self.clear_window()
        self.center_window(450, 450) # Tighter layout for just Login
        
        header = tk.Frame(self, bg="#002147", height=85)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Label(header, text="SYSTEM AUTHENTICATION", bg="#002147", fg="#ffffff", font=("Arial", 16, "bold")).pack(pady=(25, 0))

        card = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        card.place(relx=0.5, rely=0.55, anchor="center", width=380, height=300)
        tk.Label(card, text="Hardware Inventory Login", bg="#ffffff", fg="#333333", font=("Arial", 12, "bold")).pack(pady=(15, 10))

        f_usr = tk.Frame(card, bg="#ffffff")
        f_usr.pack(fill="x", padx=35, pady=5)
        tk.Label(f_usr, text="Username:", bg="#ffffff", font=("Arial", 10, "bold")).pack(anchor="w")
        self.ent_user = tk.Entry(f_usr, font=("Arial", 11), relief="solid", bg="#fafafa")
        self.ent_user.pack(fill="x", ipady=5)

        f_pwd = tk.Frame(card, bg="#ffffff")
        f_pwd.pack(fill="x", padx=35, pady=5)
        tk.Label(f_pwd, text="Password:", bg="#ffffff", font=("Arial", 10, "bold")).pack(anchor="w")
        self.ent_pass = tk.Entry(f_pwd, show="•", font=("Arial", 11), relief="solid", bg="#fafafa")
        self.ent_pass.pack(fill="x", ipady=5)

        self.show_pass_var = tk.BooleanVar()
        tk.Checkbutton(card, text="Show Password", variable=self.show_pass_var, command=self.toggle_password, bg="#ffffff", font=("Arial", 9)).pack(anchor="w", padx=35)

        f_btn = tk.Frame(card, bg="#ffffff")
        f_btn.pack(fill="x", padx=35, pady=15)
        
        tk.Button(f_btn, text="CREATE ACCOUNT", command=self.show_register_screen, bg="#e9ecef", font=("Arial", 9, "bold"), cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5)
        
        self.btn_login = tk.Button(f_btn, text="LOGIN", command=self.do_login, bg="#0d6efd", fg="#ffffff", font=("Arial", 10, "bold"), cursor="hand2")
        self.btn_login.pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=5)

    # --- 4B. REGISTER SCREEN ---
    def show_register_screen(self):
        self.clear_window()
        self.center_window(450, 520) # Taller layout to fit Email
        
        header = tk.Frame(self, bg="#002147", height=85)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Label(header, text="SYSTEM REGISTRATION", bg="#002147", fg="#ffffff", font=("Arial", 16, "bold")).pack(pady=(25, 0))

        card = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        card.place(relx=0.5, rely=0.55, anchor="center", width=380, height=370)
        tk.Label(card, text="Create New Account", bg="#ffffff", fg="#333333", font=("Arial", 12, "bold")).pack(pady=(15, 10))

        f_usr = tk.Frame(card, bg="#ffffff")
        f_usr.pack(fill="x", padx=35, pady=5)
        tk.Label(f_usr, text="Username:", bg="#ffffff", font=("Arial", 10, "bold")).pack(anchor="w")
        self.ent_user = tk.Entry(f_usr, font=("Arial", 11), relief="solid", bg="#fafafa")
        self.ent_user.pack(fill="x", ipady=5)

        f_eml = tk.Frame(card, bg="#ffffff")
        f_eml.pack(fill="x", padx=35, pady=5)
        tk.Label(f_eml, text="Email Address:", bg="#ffffff", font=("Arial", 10, "bold")).pack(anchor="w")
        self.ent_email = tk.Entry(f_eml, font=("Arial", 11), relief="solid", bg="#fafafa")
        self.ent_email.pack(fill="x", ipady=5)

        f_pwd = tk.Frame(card, bg="#ffffff")
        f_pwd.pack(fill="x", padx=35, pady=5)
        tk.Label(f_pwd, text="Password:", bg="#ffffff", font=("Arial", 10, "bold")).pack(anchor="w")
        self.ent_pass = tk.Entry(f_pwd, show="•", font=("Arial", 11), relief="solid", bg="#fafafa")
        self.ent_pass.pack(fill="x", ipady=5)

        self.show_pass_var = tk.BooleanVar()
        tk.Checkbutton(card, text="Show Password", variable=self.show_pass_var, command=self.toggle_password, bg="#ffffff", font=("Arial", 9)).pack(anchor="w", padx=35)

        f_btn = tk.Frame(card, bg="#ffffff")
        f_btn.pack(fill="x", padx=35, pady=15)
        
        tk.Button(f_btn, text="BACK TO LOGIN", command=self.show_login_screen, bg="#e9ecef", font=("Arial", 9, "bold"), cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5)
        tk.Button(f_btn, text="REGISTER", command=self.do_register, bg="#198754", fg="#ffffff", font=("Arial", 10, "bold"), cursor="hand2").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=5)

    def toggle_password(self):
        if self.show_pass_var.get():
            self.ent_pass.config(show="")
        else:
            self.ent_pass.config(show="•")

    def start_lockout_timer(self, wait_time):
        if not hasattr(self, 'btn_login') or not self.btn_login.winfo_exists():
            return
            
        if wait_time > 0:
            self.btn_login.config(state="disabled", text=f"LOCKED ({wait_time}s)", bg="#6c757d")
            self.after(1000, self.start_lockout_timer, wait_time - 1)
        else:
            self.btn_login.config(state="normal", text="LOGIN", bg="#0d6efd")

    def do_login(self):
        u, p = self.ent_user.get().strip(), self.ent_pass.get().strip()
        success, msg, wait_time = self.auth_ctrl.login(u, p)
        
        if success:
            self.current_user = u
            self.show_main_dashboard()
        elif wait_time > 0:
            self.start_lockout_timer(wait_time)
            messagebox.showwarning("Account Locked", msg)
        else:
            messagebox.showerror("Auth Alert", msg)

    def do_register(self):
        u = self.ent_user.get().strip()
        e = self.ent_email.get().strip()
        p = self.ent_pass.get().strip()
        
        success, msg = self.auth_ctrl.register(u, e, p)
        if success:
            messagebox.showinfo("Success", msg)
            self.show_login_screen() # Redirects the user back to the login page
        else:
            messagebox.showwarning("Registration Failed", msg)

    # --- 4C. MAIN INVENTORY DASHBOARD ---
    def show_main_dashboard(self):
        self.clear_window()
        self.center_window(1000, 780)
        self.selected_db_id = None
        
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background="#ffffff", foreground="#000000", rowheight=30, font=("Arial", 11))
        style.configure("Treeview.Heading", background="#e9ecef", font=("Arial", 11, "bold"))
        style.map('Treeview', background=[('selected', '#ffffff')], foreground=[('selected', '#000000')])

        head_frame = tk.Frame(self, bg="#002147", height=60)
        head_frame.pack(fill="x")
        self.lbl_valuation = tk.Label(head_frame, text="Total Asset Valuation: $0.00", bg="#002147", fg="#58d68d", font=("Arial", 14, "bold"))
        self.lbl_valuation.pack(side="left", padx=20, pady=15)
        tk.Button(head_frame, text="LOGOUT", command=self.do_logout, bg="#dc3545", fg="white", font=("Arial", 10, "bold"), relief="flat", cursor="hand2").pack(side="right", padx=20, pady=15)

        form_f = tk.LabelFrame(self, text=" Add New Hardware ", bg="#f4f6f9", fg="#002147", font=("Arial", 12, "bold"), pady=10, padx=15)
        form_f.pack(fill="x", padx=20, pady=15)

        tk.Label(form_f, text="Item Name:", bg="#f4f6f9").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.ent_h_name = tk.Entry(form_f, width=20, font=("Arial", 11))
        self.ent_h_name.grid(row=0, column=1, padx=5)

        tk.Label(form_f, text="Category:", bg="#f4f6f9").grid(row=0, column=2, padx=5, sticky="e")
        self.ent_h_cat = tk.Entry(form_f, width=15, font=("Arial", 11))
        self.ent_h_cat.grid(row=0, column=3, padx=5)

        tk.Label(form_f, text="Qty:", bg="#f4f6f9").grid(row=0, column=4, padx=5, sticky="e")
        self.ent_h_qty = tk.Entry(form_f, width=10, font=("Arial", 11))
        self.ent_h_qty.grid(row=0, column=5, padx=5)

        tk.Label(form_f, text="Price ($):", bg="#f4f6f9").grid(row=0, column=6, padx=5, sticky="e")
        self.ent_h_price = tk.Entry(form_f, width=10, font=("Arial", 11))
        self.ent_h_price.grid(row=0, column=7, padx=5)

        self.btn_save = tk.Button(form_f, text="SAVE", command=self.do_save_item, bg="#198754", fg="white", font=("Arial", 10, "bold"), width=12)
        self.btn_save.grid(row=0, column=8, padx=15)

        self.lbl_warning = tk.Label(form_f, text="", bg="#f4f6f9", fg="#dc3545", font=("Arial", 10, "bold"))
        self.lbl_warning.grid(row=1, column=0, columnspan=9, pady=5)
        
        self.ent_h_name.bind("<KeyRelease>", self.realtime_duplicate_check)

        grid_f = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        grid_f.pack(fill="both", expand=True, padx=20, pady=5)

        scroll = tk.Scrollbar(grid_f)
        self.tree = ttk.Treeview(grid_f, columns=("c0","c1","c2","c3","c4","c5","c6"), show="headings", yscrollcommand=scroll.set)
        scroll.config(command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        
        cols = ["SELECT", "ID", "NAME", "CATEGORY", "QTY", "PRICE ($)", "STATUS"]
        widths = [70, 50, 250, 150, 80, 120, 150]
        for col, head, w in zip(self.tree["columns"], cols, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor="center")

        self.tree.tag_configure("Out of Stock", background="#f8d7da", foreground="#000000")
        self.tree.tag_configure("Low Stock", background="#ffe5b4", foreground="#000000")
        self.tree.tag_configure("In Stock", background="#d4edda", foreground="#000000")
        self.tree.tag_configure("Selected", background="#002147", foreground="#ffffff")

        self.tree.bind("<ButtonRelease-1>", self.on_row_click)
        self.tree.pack(fill="both", expand=True)

        btm_f = tk.LabelFrame(self, text=" Manage Inventory ", bg="#f4f6f9", fg="#002147", font=("Arial", 12, "bold"), pady=10, padx=15)
        btm_f.pack(fill="x", padx=20, pady=15)

        tk.Label(btm_f, text="New Qty:", bg="#f4f6f9").grid(row=0, column=0, padx=5)
        self.ent_upd_qty = tk.Entry(btm_f, width=10, font=("Arial", 11))
        self.ent_upd_qty.grid(row=0, column=1, padx=5)

        tk.Label(btm_f, text="New Price ($):", bg="#f4f6f9").grid(row=0, column=2, padx=5)
        self.ent_upd_price = tk.Entry(btm_f, width=10, font=("Arial", 11))
        self.ent_upd_price.grid(row=0, column=3, padx=5)

        tk.Button(btm_f, text="UPDATE", command=self.do_update, bg="#0d6efd", fg="white", font=("Arial", 10, "bold"), width=10).grid(row=0, column=4, padx=15)
        tk.Button(btm_f, text="DELETE", command=self.do_delete, bg="#dc3545", fg="white", font=("Arial", 10, "bold"), width=10).grid(row=0, column=5, padx=15)
        tk.Button(btm_f, text="EXPORT TO CSV", command=self.do_export, bg="#212529", fg="white", font=("Arial", 10, "bold")).grid(row=0, column=6, padx=(50,0))

        self.auto_refresh()

    def do_logout(self):
        logger.info(f"User '{self.current_user}' logged out.")
        self.current_user = None
        self.show_login_screen()

    def realtime_duplicate_check(self, event=None):
        n = self.ent_h_name.get().strip()
        if n and self.inv_ctrl.check_duplicate(n):
            self.ent_h_name.config(bg="#f8d7da")
            self.btn_save.config(state="disabled", bg="#6c757d")
            self.lbl_warning.config(text=f"⚠️ '{n}' is already in inventory.")
        else:
            self.ent_h_name.config(bg="#ffffff")
            self.btn_save.config(state="normal", bg="#198754")
            self.lbl_warning.config(text="")

    def on_row_click(self, event):
        item = self.tree.focus()
        if not item: return
        values = self.tree.item(item, "values")
        if values:
            cid = int(values[1])
            if self.selected_db_id == cid:
                self.selected_db_id = None
                self.ent_upd_qty.delete(0, tk.END)
                self.ent_upd_price.delete(0, tk.END)
            else:
                self.selected_db_id = cid
                self.ent_upd_qty.delete(0, tk.END)
                self.ent_upd_qty.insert(0, values[4])
                self.ent_upd_price.delete(0, tk.END)
                self.ent_upd_price.insert(0, values[5].replace('$', ''))
            self.sync_table()

    def do_save_item(self):
        n = self.ent_h_name.get().strip()
        success, msg = self.inv_ctrl.add_item(n, self.ent_h_cat.get(), self.ent_h_qty.get(), self.ent_h_price.get())
        if success:
            self.ent_h_name.delete(0, tk.END)
            self.ent_h_cat.delete(0, tk.END)
            self.ent_h_qty.delete(0, tk.END)
            self.ent_h_price.delete(0, tk.END)
            self.selected_db_id = None
            self.sync_table()
        else:
            messagebox.showerror("Error", msg)

    def do_update(self):
        if not self.selected_db_id: return messagebox.showwarning("Error", "Tick an item to update.")
        success, msg = self.inv_ctrl.update_item(self.selected_db_id, self.ent_upd_qty.get(), self.ent_upd_price.get())
        if success:
            self.selected_db_id = None
            self.ent_upd_qty.delete(0, tk.END)
            self.ent_upd_price.delete(0, tk.END)
            self.sync_table()
        else:
            messagebox.showerror("Error", msg)

    def do_delete(self):
        if not self.selected_db_id: return messagebox.showwarning("Error", "Tick an item to delete.")
        if messagebox.askyesno("Confirm", "Permanently delete this item?"):
            self.inv_ctrl.delete_item(self.selected_db_id)
            self.selected_db_id = None
            self.ent_upd_qty.delete(0, tk.END)
            self.ent_upd_price.delete(0, tk.END)
            self.sync_table()

    def do_export(self):
        success, msg = self.inv_ctrl.export_csv()
        if success: messagebox.showinfo("Export Success", msg)
        else: messagebox.showerror("Export Failed", msg)

    def sync_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        data = self.inv_ctrl.fetch_all()
        for d in data:
            db_id, name, cat, qty, price, status = d
            price_fmt = f"${price:,.2f}"
            
            if self.selected_db_id == db_id:
                tick, tag = "☑", "Selected"
            else:
                tick, tag = "☐", status
                
            self.tree.insert("", "end", values=(tick, db_id, name, cat, qty, price_fmt, status), tags=(tag,))
            
        total_val = self.inv_ctrl.get_total_valuation()
        self.lbl_valuation.config(text=f"Total Asset Valuation: ${total_val:,.2f}")
        self.realtime_duplicate_check()

    def auto_refresh(self):
        self.sync_table()
        self.refresh_job = self.after(2000, self.auto_refresh)

# ==========================================
# 5. EXECUTION
# ==========================================
if __name__ == "__main__":
    init_db()
    app = HardwareApp()
    app.mainloop()