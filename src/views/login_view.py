import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from pathlib import Path
import os

class LoginView(tk.Toplevel):

    def __init__(self, parent=None, on_login_success=None):
        if parent:
            super().__init__(parent)
        else:
            self.root = tk.Tk()
            self.root.withdraw()
            super().__init__(self.root)
            self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.on_login_success = on_login_success
        self.title('Hệ thống phát hiện và phân loại tàu thuyền...')
        self.geometry('420x550')
        self.configure(bg='white')
        self.resizable(False, False)
        self.center_window(420, 550)
        self.username_var = tk.StringVar(value='admin')
        self.password_var = tk.StringVar(value='1')
        self.show_password = False
        self.setup_ui()

    def center_window(self, width, height):
        self.update_idletasks()
        x = self.winfo_screenwidth() // 2 - width // 2
        y = self.winfo_screenheight() // 2 - height // 2
        self.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    def setup_ui(self):
        main_frame = tk.Frame(self, bg='white')
        main_frame.pack(expand=True, fill='both', padx=40, pady=20)
        project_root = Path(__file__).resolve().parent.parent.parent
        logo_path = project_root / 'picture' / 'logo.png'
        try:
            img = Image.open(logo_path)
            img = img.resize((120, 120), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
            self.iconphoto(False, self.logo_img)
            logo_label = tk.Label(main_frame, image=self.logo_img, bg='white')
            logo_label.pack(pady=(10, 10))
        except Exception as e:
            print(f'Không thể tải logo: {e}')
            logo_label = tk.Label(main_frame, text='[LOGO VMU]', bg='white', fg='blue', font=('Arial', 20, 'bold'))
            logo_label.pack(pady=(10, 10))
        title_label = tk.Label(main_frame, text='TRƯỜNG ĐẠI HỌC HÀNG HẢI VIỆT NAM', font=('Arial', 12, 'bold'), bg='white', fg='#000000')
        title_label.pack(pady=(10, 5))
        subtitle_label = tk.Label(main_frame, text='Hệ thống phát hiện và phân loại tàu thuyền', font=('Arial', 10), bg='white', fg='#666666')
        subtitle_label.pack(pady=(0, 30))
        user_label = tk.Label(main_frame, text='Tên đăng nhập', font=('Arial', 10), bg='white', fg='#666666')
        user_label.pack(anchor='w', pady=(0, 5))
        user_border_frame = tk.Frame(main_frame, bg='#cccccc', padx=1, pady=1)
        user_border_frame.pack(fill='x', pady=(0, 15))
        user_inner_frame = tk.Frame(user_border_frame, bg='#f9f9f9')
        user_inner_frame.pack(fill='both', expand=True)
        user_entry = tk.Entry(user_inner_frame, textvariable=self.username_var, font=('Arial', 12), bg='#f9f9f9', relief='flat', insertbackground='black')
        user_entry.pack(fill='both', expand=True, ipady=6, padx=5, pady=2)
        user_entry.focus()
        pass_label = tk.Label(main_frame, text='Mật khẩu', font=('Arial', 10), bg='white', fg='#666666')
        pass_label.pack(anchor='w', pady=(0, 5))
        pass_border_frame = tk.Frame(main_frame, bg='#cccccc', padx=1, pady=1)
        pass_border_frame.pack(fill='x', pady=(0, 30))
        pass_inner_frame = tk.Frame(pass_border_frame, bg='#f9f9f9')
        pass_inner_frame.pack(fill='both', expand=True)
        self.pass_entry = tk.Entry(pass_inner_frame, textvariable=self.password_var, font=('Arial', 12), show='*', bg='#f9f9f9', relief='flat', insertbackground='black')
        self.pass_entry.pack(side='left', fill='both', expand=True, ipady=6, padx=5, pady=2)
        self.eye_label = tk.Label(pass_inner_frame, text='👁', font=('Arial', 12), bg='#f9f9f9', fg='#666666', cursor='hand2')
        self.eye_label.pack(side='right', padx=10)
        self.eye_label.bind('<Button-1>', self.toggle_password)
        login_btn = tk.Button(main_frame, text='ĐĂNG NHẬP', font=('Arial', 12, 'bold'), bg='#007BFF', fg='white', activebackground='#0056b3', activeforeground='white', relief='flat', cursor='hand2', command=self.handle_login)
        login_btn.pack(fill='x', ipady=10, padx=40)
        self.bind('<Return>', lambda event: self.handle_login())

    def toggle_password(self, event=None):
        self.show_password = not self.show_password
        if self.show_password:
            self.pass_entry.config(show='')
            self.eye_label.config(fg='#007BFF')
        else:
            self.pass_entry.config(show='*')
            self.eye_label.config(fg='#666666')

    def handle_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        if not username or not password:
            messagebox.showwarning('Cảnh báo', 'Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu!', parent=self)
            return
        if self.on_login_success:
            self.on_login_success(username, password)
        else:
            messagebox.showinfo('Thông báo', f'Đăng nhập thành công với tài khoản: {username}', parent=self)
            self.on_close()

    def on_close(self):
        self.destroy()
        try:
            self.master.destroy()
        except:
            pass
if __name__ == '__main__':
    app = LoginView()
    app.mainloop()
