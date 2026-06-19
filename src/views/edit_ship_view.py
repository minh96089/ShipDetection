import tkinter as tk
from tkinter import filedialog, ttk
import os

class EditShipView(tk.Toplevel):

    def __init__(self, parent, class_options):
        super().__init__(parent)
        self.title('Sửa thông tin tàu')
        self.geometry('550x650')
        self.resizable(False, False)
        self.grab_set()
        self.colors = {'bg': '#f8f9fa', 'primary': '#3498db', 'success': '#f39c12', 'text': '#2c3e50'}
        self.config(bg=self.colors['bg'])
        self.class_options = class_options
        self.save_command = None
        self.temp_image_path = tk.StringVar()
        self.setup_ui()

    def setup_ui(self):
        self.create_header()
        form_frame = tk.Frame(self, bg='white')
        form_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)
        tk.Label(form_frame, text='Số hiệu tàu (Không thể sửa)', font=('Segoe UI', 11, 'bold'), bg='white', fg='#7f8c8d').pack(anchor='w', pady=(0, 5))
        self.e_sohieu = tk.Entry(form_frame, font=('Segoe UI', 11), width=40, bd=1, relief='solid')
        self.e_sohieu.pack(fill=tk.X, pady=(0, 15))
        tk.Label(form_frame, text='Loại tàu', font=('Segoe UI', 11, 'bold'), bg='white', fg=self.colors['text']).pack(anchor='w', pady=(0, 5))
        self.e_class = ttk.Combobox(form_frame, font=('Segoe UI', 11), values=self.class_options, state='readonly', width=38)
        self.e_class.set(self.class_options[0] if self.class_options else '')
        self.e_class.pack(fill=tk.X, pady=(0, 15))
        tk.Label(form_frame, text='Đổi ảnh đại diện (để trống nếu giữ nguyên)', font=('Segoe UI', 11, 'bold'), bg='white', fg=self.colors['text']).pack(anchor='w', pady=(0, 5))
        self.create_image_selector(form_frame)
        tk.Label(form_frame, text='Mô tả', font=('Segoe UI', 11, 'bold'), bg='white', fg=self.colors['text']).pack(anchor='w', pady=(0, 5))
        self.create_description_field(form_frame)
        btn_frame = tk.Frame(self, bg=self.colors['bg'])
        btn_frame.pack(fill=tk.X, padx=25, pady=(0, 20))
        save_btn = tk.Button(btn_frame, text='💾 LƯU THAY ĐỔI', bg=self.colors['success'], fg='white', font=('Segoe UI', 12, 'bold'), bd=0, padx=30, pady=10, cursor='hand2', command=self.on_save_clicked)
        save_btn.pack(fill=tk.X)

        def on_enter(e):
            save_btn.config(bg='#e67e22')

        def on_leave(e):
            save_btn.config(bg=self.colors['success'])
        save_btn.bind('<Enter>', on_enter)
        save_btn.bind('<Leave>', on_leave)

    def create_header(self):
        header = tk.Frame(self, bg=self.colors['success'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text='✏️ SỬA THÔNG TIN TÀU', font=('Segoe UI', 16, 'bold'), bg=self.colors['success'], fg='white').pack(pady=15)

    def create_image_selector(self, parent):
        img_frame = tk.Frame(parent, bg='white')
        img_frame.pack(fill=tk.X, pady=(0, 20))
        self.e_anh = tk.Entry(img_frame, font=('Segoe UI', 10), textvariable=self.temp_image_path, width=30, state='readonly', bd=1, relief='solid')
        self.e_anh.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        def browse_image():
            p = filedialog.askopenfilename(filetypes=[('Image files', '*.jpg *.jpeg *.png *.bmp')])
            if p:
                self.temp_image_path.set(p)
        browse_btn = tk.Button(img_frame, text='📂 Chọn file', command=browse_image, bg=self.colors['primary'], fg='white', font=('Segoe UI', 10, 'bold'), bd=0, padx=15, pady=6, cursor='hand2')
        browse_btn.pack(side=tk.LEFT)

    def create_description_field(self, parent):
        desc_frame = tk.Frame(parent, bg='white')
        desc_frame.pack(fill=tk.X, pady=(0, 15))
        scrollbar = tk.Scrollbar(desc_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.e_description = tk.Text(desc_frame, font=('Segoe UI', 10), height=4, width=45, bd=1, relief='solid', yscrollcommand=scrollbar.set)
        self.e_description.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.e_description.yview)

    def load_data(self, ship_data):
        self.e_sohieu.insert(0, ship_data.get('so_hieu', ''))
        self.e_sohieu.config(state='disabled')
        self.e_class.set(ship_data.get('class_name', ''))
        mo_ta = ship_data.get('mo_ta', '')
        if mo_ta and mo_ta != 'Không có mô tả':
            self.e_description.insert('1.0', mo_ta)

    def get_data(self):
        so_hieu = self.e_sohieu.get().strip()
        class_name = self.e_class.get()
        anh_dai_dien_moi = self.temp_image_path.get()
        mo_ta = self.e_description.get('1.0', tk.END).strip()
        if not mo_ta:
            mo_ta = 'không có mô tả'
        return {'so_hieu': so_hieu, 'class_name': class_name, 'anh_dai_dien_moi': anh_dai_dien_moi, 'mo_ta': mo_ta}

    def set_save_command(self, command):
        self.save_command = command

    def on_save_clicked(self):
        if self.save_command:
            self.save_command()

    def close_dialog(self):
        self.destroy()
