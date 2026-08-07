import tkinter as tk
from tkinter import messagebox, ttk
from controllers.auth_controller import AuthController

class LoginWindow:
    def __init__(self, root, on_login_success):
        self.root = root
        self.on_login_success = on_login_success
        self.auth = AuthController()
        
        # --- Industry-Level Window Configuration ---
        self.root.title("University Secure Portal - Auth")
        window_width, window_height = 450, 420
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int((screen_width / 2) - (window_width / 2))
        center_y = int((screen_height / 2) - (window_height / 2))
        
        self.root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        self.root.resizable(False, False)
        self.root.configure(bg="#f4f6f9")
        
        self._construct_ui()

    def _construct_ui(self):
        # Top Branding Header
        header_frame = tk.Frame(self.root, bg="#002147", height=85)
        header_frame.pack(fill="x", side="top")
        header_frame.pack_propagate(False)
        
        # ERROR FIXED HERE: Removed tracking=2
        tk.Label(header_frame, text="AEGIS AUTHENTICATION", bg="#002147", fg="#ffffff", 
                 font=("Arial", 16, "bold")).pack(pady=(25, 0))

        # Central Login Card
        card_frame = tk.Frame(self.root, bg="#ffffff", bd=1, relief="solid")
        card_frame.place(relx=0.5, rely=0.58, anchor="center", width=360, height=270)
        
        tk.Label(card_frame, text="Secure Portal Login", bg="#ffffff", fg="#333333", 
                 font=("Arial", 12, "bold")).pack(pady=(20, 15))

        # Username Field
        user_frame = tk.Frame(card_frame, bg="#ffffff")
        user_frame.pack(fill="x", padx=35, pady=5)
        tk.Label(user_frame, text="Username:", bg="#ffffff", fg="#666666", font=("Arial", 10, "bold")).pack(anchor="w")
        self.entry_user = tk.Entry(user_frame, font=("Arial", 11), relief="solid", borderwidth=1, bg="#fafafa")
        self.entry_user.pack(fill="x", pady=(2, 0), ipady=5)

        # Password Field
        pass_frame = tk.Frame(card_frame, bg="#ffffff")
        pass_frame.pack(fill="x", padx=35, pady=5)
        tk.Label(pass_frame, text="Password:", bg="#ffffff", fg="#666666", font=("Arial", 10, "bold")).pack(anchor="w")
        self.entry_pass = tk.Entry(pass_frame, show="•", font=("Arial", 11), relief="solid", borderwidth=1, bg="#fafafa")
        self.entry_pass.pack(fill="x", pady=(2, 0), ipady=5)

        # Button Group
        btn_frame = tk.Frame(card_frame, bg="#ffffff")
        btn_frame.pack(fill="x", padx=35, pady=20)
        
        tk.Button(btn_frame, text="REGISTER", command=self.handle_register, bg="#e9ecef", fg="#333333", 
                  font=("Arial", 10, "bold"), relief="flat", cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5)
        tk.Button(btn_frame, text="SECURE LOGIN", command=self.handle_login, bg="#0d6efd", fg="#ffffff", 
                  font=("Arial", 10, "bold"), relief="flat", cursor="hand2").pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=5)

    def handle_login(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()
        
        success, msg = self.auth.login_user(username, password)
        if success:
            self.on_login_success()
        else:
            messagebox.showerror("Authentication Failed", msg)

    def handle_register(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()
        
        success, msg = self.auth.register_user(username, password)
        if success:
            messagebox.showinfo("Success", msg)
            self.entry_user.delete(0, tk.END)
            self.entry_pass.delete(0, tk.END)
        else:
            messagebox.showwarning("Registration Alert", msg)