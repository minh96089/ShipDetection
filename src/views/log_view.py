import tkinter as tk
from tkinter import messagebox, ttk
import cv2
from PIL import Image, ImageTk
import os

class LogView:

    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.frame = tk.Frame(parent_frame, bg='#ecf0f1')
        self.frame.grid(row=0, column=0, sticky='nsew')
        self.tree_img_paths = {}
        self.tk_db_img = None
        self.setup_ui()

    def setup_ui(self):
        header_frame = tk.Frame(self.frame, bg='#ecf0f1')
        header_frame.pack(fill=tk.X, padx=20, pady=15)
        tk.Label(header_frame, text='NHẬT KÝ PHÁT HIỆN', font=('Arial', 18, 'bold'), bg='#ecf0f1').pack(side=tk.LEFT)
        self.refresh_status = tk.Label(header_frame, text='', fg='#3498db', bg='#ecf0f1', font=('Arial', 10, 'italic'))
        self.refresh_status.pack(side=tk.RIGHT, padx=10)
        self.refresh_button = tk.Button(header_frame, text='🔄 Làm mới (F5)', bg='#3498db', fg='white', font=('Arial', 11, 'bold'), padx=15, pady=5, relief='flat', cursor='hand2')
        self.refresh_button.pack(side=tk.RIGHT)
        search_frame = tk.Frame(header_frame, bg='#ecf0f1')
        search_frame.pack(side=tk.RIGHT, padx=20)
        self.search_btn = tk.Button(search_frame, text='🔍 Tìm', bg='#2ecc71', fg='white', font=('Arial', 10, 'bold'), relief='flat', cursor='hand2')
        self.search_btn.pack(side=tk.RIGHT, padx=(5, 0))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Combobox(search_frame, textvariable=self.search_var, font=('Arial', 11), width=16)
        self.search_entry.pack(side=tk.RIGHT, padx=5)
        self.search_type = ttk.Combobox(search_frame, values=['Số hiệu', 'Loại tàu'], state='readonly', width=10, font=('Arial', 10))
        self.search_type.set('Số hiệu')
        self.search_type.pack(side=tk.RIGHT, padx=5)
        tk.Label(search_frame, text='Tìm kiếm:', font=('Arial', 11, 'bold'), bg='#ecf0f1', fg='#2c3e50').pack(side=tk.RIGHT, padx=5)

        def on_search_type_change(event=None):
            if self.search_type.get() == 'Loại tàu':
                self.search_entry.config(values=['fishing boat', 'speed boat', 'passenger ship'], state='readonly')
                self.search_var.set('')
            else:
                self.search_entry.config(values=[], state='normal')
                self.search_var.set('')
        self.search_type.bind('<<ComboboxSelected>>', on_search_type_change)
        main_frame = tk.Frame(self.frame, bg='#ecf0f1')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        tree_frame = tk.Frame(main_frame, bg='#ecf0f1')
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=('ID', 'Class', 'SoHieuOCR', 'Gio', 'Video', 'GhiChu'), show='headings', height=20)
        self.tree.heading('ID', text='ID Tracking')
        self.tree.heading('Class', text='Loại tàu')
        self.tree.heading('SoHieuOCR', text='Số hiệu (OCR)')
        self.tree.heading('Gio', text='Giờ phát hiện')
        self.tree.heading('Video', text='Nguồn video')
        self.tree.heading('GhiChu', text='📝 Ghi chú')
        for col, w in zip(['ID', 'Class', 'SoHieuOCR', 'Gio', 'Video', 'GhiChu'], [80, 140, 130, 160, 200, 160]):
            self.tree.column(col, anchor=tk.CENTER, width=w)
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        img_panel = tk.Frame(main_frame, bg='white', width=320, relief='ridge', bd=2)
        img_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0))
        img_panel.pack_propagate(False)
        tk.Label(img_panel, text='🚢 ẢNH TÀU', font=('Arial', 13, 'bold'), bg='white').pack(pady=12)
        self.db_img_canvas = tk.Canvas(img_panel, width=290, height=260, bg='#dddddd')
        self.db_img_canvas.pack(pady=5, padx=10)
        self.db_img_canvas.create_text(145, 130, text='Chọn một hàng\nđể xem ảnh', fill='gray', font=('Arial', 12))
        self.db_info_label = tk.Label(img_panel, text='', font=('Arial', 10), bg='white', wraplength=290, justify=tk.LEFT)
        self.db_info_label.pack(pady=8, padx=10)
        btn_frame = tk.Frame(img_panel, bg='white')
        btn_frame.pack(pady=12)
        self.manual_ocr_btn = tk.Button(btn_frame, text='⚡ OCR Thủ công', bg='#27ae60', fg='white', font=('Arial', 10, 'bold'), width=15, height=2)
        self.manual_ocr_btn.pack(side=tk.LEFT, padx=5)
        self.edit_ghi_chu_btn = tk.Button(btn_frame, text='✏️ Sửa ghi chú', bg='#2980b9', fg='white', font=('Arial', 10, 'bold'), width=15, height=2)
        self.edit_ghi_chu_btn.pack(side=tk.LEFT, padx=5)
        self.ship_history_tree = ttk.Treeview(self.frame, columns=('Gio', 'SoHieu', 'Video'), show='headings', height=5)
        self.ship_history_tree.heading('Gio', text='Giờ phát hiện')
        self.ship_history_tree.heading('SoHieu', text='Số hiệu (OCR)')
        self.ship_history_tree.heading('Video', text='Nguồn video')

    def refresh_database_ui(self, rows):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.tree_img_paths.clear()
        if not hasattr(self, 'tree_unique_ids'):
            self.tree_unique_ids = {}
        self.tree_unique_ids.clear()
        self.db_img_canvas.delete('all')
        self.db_img_canvas.create_text(145, 130, text='Chọn một hàng\nđể xem ảnh', fill='gray', font=('Arial', 12))
        self.db_info_label.config(text='')
        for row in rows:
            ghi_chu = row[7] if len(row) > 7 else ''
            item_id = self.tree.insert('', tk.END, values=(row[0], row[1], row[2], row[3], row[5], ghi_chu or ''))
            self.tree_img_paths[item_id] = row[4]
            if len(row) > 6:
                self.tree_unique_ids[item_id] = row[6]

    def show_db_info(self, info, img_path):
        self.db_info_label.config(text=info)
        self.db_img_canvas.delete('all')
        if img_path and os.path.exists(img_path):
            try:
                img = cv2.imread(img_path)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = cv2.resize(img, (290, 260))
                self.tk_db_img = ImageTk.PhotoImage(image=Image.fromarray(img))
                self.db_img_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_db_img)
            except:
                self.db_img_canvas.create_text(145, 130, text='⚠️ Lỗi load ảnh', fill='red', font=('Arial', 12))
        else:
            self.db_img_canvas.create_text(145, 130, text='📷 Không có ảnh', fill='gray', font=('Arial', 12))

    def get_frame(self):
        return self.frame
