import tkinter as tk
from tkinter import messagebox, ttk
import cv2
from PIL import Image, ImageTk
import os

class ShipView:

    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.colors = {'bg': '#f4f7f6', 'sidebar_bg': '#ffffff', 'primary': '#3498db', 'success': '#2ecc71', 'danger': '#e74c3c', 'text': '#2c3e50', 'header': '#ffffff'}
        self.frame = tk.Frame(parent_frame, bg=self.colors['bg'])
        self.frame.grid(row=0, column=0, sticky='nsew')
        self.ship_img_paths = {}
        self.tk_ship_img = None
        self.configure_styles()
        self.setup_ui()

    def configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Treeview', background='white', foreground=self.colors['text'], rowheight=35, fieldbackground='white', font=('Segoe UI', 10))
        style.configure('Treeview.Heading', background='#ebf2f6', foreground=self.colors['text'], font=('Segoe UI', 10, 'bold'), borderwidth=0)
        style.map('Treeview', background=[('selected', self.colors['primary'])])

    def create_modern_button(self, parent, text, color, command=None):
        btn = tk.Button(parent, text=text, bg=color, fg='white', font=('Segoe UI', 10, 'bold'), bd=0, padx=20, pady=8, cursor='hand2', activebackground=color, activeforeground='white', command=command)

        def on_enter(e):
            btn['background'] = self.lighten_color(color, 0.2)

        def on_leave(e):
            btn['background'] = color
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        return btn

    def lighten_color(self, hex_color, factor):
        hex_color = hex_color.lstrip('#')
        rgb = tuple((int(hex_color[i:i + 2], 16) for i in (0, 2, 4)))
        new_rgb = [min(255, int(c + (255 - c) * factor)) for c in rgb]
        return '#%02x%02x%02x' % tuple(new_rgb)

    def setup_ui(self):
        header_frame = tk.Frame(self.frame, bg=self.colors['header'], height=70)
        header_frame.pack(fill=tk.X, padx=0, pady=(0, 20))
        header_frame.pack_propagate(False)
        line = tk.Frame(self.frame, bg='#e0e0e0', height=1)
        line.pack(fill=tk.X)
        tk.Label(header_frame, text='🚢 HỆ THỐNG QUẢN LÝ TÀU', font=('Segoe UI', 16, 'bold'), bg=self.colors['header'], fg=self.colors['text']).pack(side=tk.LEFT, padx=30)
        self.ship_refresh_status = tk.Label(header_frame, text='', fg=self.colors['success'], bg=self.colors['header'], font=('Segoe UI', 10, 'italic'))
        self.ship_refresh_status.pack(side=tk.RIGHT, padx=10)
        self.refresh_button = tk.Button(header_frame, text='🔄 Làm mới (F5)', bg=self.colors['primary'], fg='white', font=('Arial', 11, 'bold'), padx=15, pady=5, relief='flat', cursor='hand2')
        self.refresh_button.pack(side=tk.RIGHT)
        main_container = tk.Frame(self.frame, bg=self.colors['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=0)
        left_frame = tk.Frame(main_container, bg=self.colors['bg'])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.add_ship_btn = self.create_modern_button(left_frame, '➕ THÊM TÀU MỚI', self.colors['success'])
        self.add_ship_btn.pack(anchor='w', pady=(0, 15))
        tree_container = tk.Frame(left_frame, bg='white', bd=1, relief='flat')
        tree_container.pack(fill=tk.BOTH, expand=True)
        self.ship_tree = ttk.Treeview(tree_container, columns=('SoHieu', 'Class', 'NgayTao', 'ThaoCac'), show='headings')
        self.ship_tree.heading('SoHieu', text='SỐ HIỆU')
        self.ship_tree.heading('Class', text='LOẠI TÀU')
        self.ship_tree.heading('NgayTao', text='NGÀY TẠO')
        self.ship_tree.heading('ThaoCac', text='THAO TÁC')
        for col, w in zip(['SoHieu', 'Class', 'NgayTao', 'ThaoCac'], [110, 110, 110, 180]):
            self.ship_tree.column(col, width=w, anchor='center')
        self.ship_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_panel = tk.Frame(main_container, bg=self.colors['bg'], width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(30, 0))
        right_panel.pack_propagate(False)
        self.detail_card = tk.Frame(right_panel, bg='white', bd=0)
        self.detail_card.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.detail_card, text='Thông tin chi tiết', font=('Segoe UI', 12, 'bold'), bg='white', fg=self.colors['text']).pack(pady=(15, 10))
        self.ship_img_canvas = tk.Canvas(self.detail_card, width=350, height=220, bg='#f8f9fa', highlightthickness=1, highlightbackground='#eeeeee')
        self.ship_img_canvas.pack(pady=10, padx=20)
        self.ship_img_canvas.create_text(175, 110, text='Chưa có dữ liệu hình ảnh', fill='#95a5a6', font=('Segoe UI', 9))
        self.ship_info_label = tk.Label(self.detail_card, text='Vui lòng chọn một tàu từ danh sách để xem chi tiết thông tin và lịch sử.', font=('Segoe UI', 10), bg='white', fg='#7f8c8d', wraplength=320, justify=tk.LEFT, pady=20)
        self.ship_info_label.pack(fill=tk.X, padx=20)
        tk.Label(self.detail_card, text='Lịch sử phát hiện', font=('Segoe UI', 11, 'bold'), bg='white', fg=self.colors['text']).pack(pady=(10, 5))
        hist_frame = tk.Frame(self.detail_card, bg='white')
        hist_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.ship_history_tree = ttk.Treeview(hist_frame, columns=('ThoiGian', 'PhanLoai', 'DoTinCay'), show='headings', height=5)
        self.ship_history_tree.heading('ThoiGian', text='THỜI GIAN')
        self.ship_history_tree.heading('PhanLoai', text='PHÂN LOẠI')
        self.ship_history_tree.heading('DoTinCay', text='ĐỘ TIN CẬY')
        self.ship_history_tree.column('ThoiGian', width=120, anchor='center')
        self.ship_history_tree.column('PhanLoai', width=80, anchor='center')
        self.ship_history_tree.column('DoTinCay', width=60, anchor='center')
        self.ship_history_tree.pack(fill=tk.BOTH, expand=True)

    def refresh_ship_list_ui(self, rows):
        for i in self.ship_tree.get_children():
            self.ship_tree.delete(i)
        self.ship_img_paths.clear()
        for row in rows:
            item_id = self.ship_tree.insert('', tk.END, values=(row[1], row[2], row[5], 'Sửa | Xóa'))
            self.ship_img_paths[item_id] = row[4]

    def show_ship_info(self, info, img_path):
        self.ship_info_label.config(text=info, fg=self.colors['text'], font=('Arial', 10))
        self.ship_img_canvas.delete('all')
        if img_path and os.path.exists(img_path):
            try:
                img = cv2.imread(img_path)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = cv2.resize(img, (350, 220))
                self.tk_ship_img = ImageTk.PhotoImage(image=Image.fromarray(img))
                self.ship_img_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_ship_img)
            except Exception:
                self.ship_img_canvas.create_text(175, 110, text='⚠️ Lỗi định dạng ảnh', fill=self.colors['danger'])
        else:
            self.ship_img_canvas.create_text(175, 110, text='📷 Không có ảnh đại diện', fill='#95a5a6')

    def get_frame(self):
        return self.frame
