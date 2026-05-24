import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
import os
from src.views.log_view import LogView
from src.views.ship_view import ShipView
from src.views.report_view import ReportView
from src.views.alerts_view import AlertsView
CLASS_OPTIONS = ['speed boat', 'passenger ship', 'fishing boat']

class MainView:

    def __init__(self, root, callbacks):
        self.root = root
        self.callbacks = callbacks
        self.engine = None
        self.root.title('Hệ thống phát hiện và phân loại tàu thuyền')
        self.root.geometry('1400x900')
        self.output_dir = tk.StringVar()
        self.model_path = tk.StringVar()
        self.ocr_model_path = tk.StringVar()
        self.video_path = tk.StringVar()
        self.tracker_path = tk.StringVar(value='bytetrack.yml')
        self.conf_val = tk.DoubleVar(value=0.5)
        self.use_ocr_var = tk.BooleanVar(value=True)
        self.use_tracking_trace_var = tk.BooleanVar(value=True)
        self.tree_img_paths = {}
        self.tracker_files = []
        self.roi_original_points = []
        self.drawing_roi = False
        self.roi_closed = False
        self.last_frame = None
        self.last_scale = 1.0
        self.last_offset = (0, 0)
        self.tk_img = None
        self.tk_crop = None
        self.tk_db_img = None
        self.zoom_level = 1.0
        self.zoom_min = 1.0
        self.zoom_max = 8.0
        self.pan_x = 0
        self.pan_y = 0
        self._pan_start = None
        self.model_files = []
        self.ocr_model_files = []
        self.setup_navbar()
        self.container = tk.Frame(self.root)
        self.container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.frames = {}
        self.setup_monitoring_page()
        self.load_trackers()
        self.setup_combobox_bindings()
        self.load_default_directories()
        self.log_view = LogView(self.container)
        self.frames['database'] = self.log_view.get_frame()
        self.log_view.refresh_button.config(command=self.callbacks['refresh_database'])
        self.log_view.search_btn.config(command=self.callbacks['refresh_database'])
        self.log_view.search_entry.bind('<Return>', lambda e: self.callbacks['refresh_database']())
        self.log_view.search_entry.bind('<<ComboboxSelected>>', lambda e: self.callbacks['refresh_database']())
        self.log_view.manual_ocr_btn.config(command=self.callbacks['manual_ocr'])
        self.log_view.tree.bind('<<TreeviewSelect>>', self.callbacks['on_tree_select'])
        self.ship_view = ShipView(self.container)
        self.frames['ships'] = self.ship_view.get_frame()
        if 'refresh_ships' in self.callbacks:
            self.ship_view.refresh_button.config(command=self.callbacks['refresh_ships'])
        self.report_view = ReportView(self.container)
        self.frames['reports'] = self.report_view.get_frame()
        from src.views.statistics_view import StatisticsView
        self.statistics_view = StatisticsView(self.container)
        self.frames['statistics'] = self.statistics_view.get_frame()
        self.alerts_view = AlertsView(self.container)
        self.frames['alerts'] = self.alerts_view.get_frame()
        self.show_frame('monitoring')
        self.root.bind('<F5>', lambda e: self.callbacks['refresh_current_page']())
        self.root.protocol('WM_DELETE_WINDOW', self.callbacks['on_closing'])

    def setup_navbar(self):
        navbar = tk.Frame(self.root, bg='#2c3e50', height=50)
        navbar.pack(side=tk.TOP, fill=tk.X)
        nav_style = {'bg': '#2c3e50', 'fg': 'white', 'font': ('Arial', 11, 'bold'), 'relief': 'flat', 'activebackground': '#34495e', 'activeforeground': 'white', 'padx': 20}
        tk.Button(navbar, text='Hệ thống giám sát', **nav_style, command=lambda: self.show_frame('monitoring')).pack(side=tk.LEFT)
        tk.Button(navbar, text='Nhật ký phát hiện', **nav_style, command=lambda: self.show_frame('database')).pack(side=tk.LEFT)
        tk.Button(navbar, text='Quản lý tàu', **nav_style, command=lambda: self.show_frame('ships')).pack(side=tk.LEFT)
        tk.Button(navbar, text='Quản lý Vi phạm', **nav_style, command=lambda: self.show_frame('alerts')).pack(side=tk.LEFT)
        tk.Button(navbar, text='Báo cáo', **nav_style, command=lambda: self.show_frame('reports')).pack(side=tk.LEFT)
        tk.Button(navbar, text='Thống kê', **nav_style, command=lambda: self.show_frame('statistics')).pack(side=tk.LEFT)

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        if page_name == 'database':
            self.callbacks['refresh_current_page']()
        elif page_name == 'alerts' and hasattr(self, 'alerts_view'):
            self.alerts_view.refresh_alerts()

    def setup_monitoring_page(self):
        page = tk.Frame(self.container, bg='#f8f9fa')
        self.frames['monitoring'] = page
        page.grid(row=0, column=0, sticky='nsew')
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        left_wrapper = tk.Frame(page, bg='#f8f9fa')
        left_wrapper.grid_rowconfigure(0, weight=1)
        left_wrapper.grid_rowconfigure(1, weight=0)
        left_wrapper.grid_rowconfigure(2, weight=0)
        left_wrapper.grid_columnconfigure(0, weight=1)
        self.canvas_video = tk.Canvas(left_wrapper, bg='black')
        self.canvas_video.grid(row=0, column=0, sticky='nsew')
        self.canvas_video.bind('<Button-1>', self.callbacks['on_canvas_click'])
        self.canvas_video.bind('<MouseWheel>', self._on_zoom)
        self.canvas_video.bind('<Button-4>', self._on_zoom)
        self.canvas_video.bind('<Button-5>', self._on_zoom)
        self.canvas_video.bind('<Button-2>', self._pan_start_drag)
        self.canvas_video.bind('<B2-Motion>', self._pan_do_drag)
        self.canvas_video.bind('<ButtonRelease-2>', self._pan_end_drag)
        self.alert_label = tk.Label(left_wrapper, text='', font=('Segoe UI', 11, 'bold'), fg='red', bg='#f8f9fa')
        self.alert_label.grid(row=2, column=0, sticky='ew', pady=(5, 0))
        progress_outer = tk.Frame(left_wrapper, bg='#f8f9fa', pady=4)
        progress_outer.grid(row=1, column=0, sticky='ew')
        self.reset_zoom_btn = tk.Button(progress_outer, text='🔍 Reset Zoom', font=('Segoe UI', 8), bg='#ecf0f1', fg='#2c3e50', relief='flat', cursor='hand2', padx=8, command=self.reset_zoom)
        self.reset_zoom_btn.pack(side=tk.RIGHT, padx=(5, 0))
        self.progress_label = tk.Label(progress_outer, text='Frame: 0 / 0  (0%)', font=('Segoe UI', 9), bg='#f8f9fa', fg='#2c3e50')
        self.progress_label.pack(side=tk.RIGHT, padx=(0, 8))
        self.progress_bar = ttk.Progressbar(progress_outer, orient='horizontal', mode='determinate', maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        right_panel = tk.Frame(page, bg='#ffffff', relief='flat', bd=0)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=8, pady=10)
        left_wrapper.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        right_panel.pack_propagate(False)
        right_panel.config(width=380)
        right_panel.grid_rowconfigure(0, weight=0)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        control_frame = tk.Frame(right_panel, bg='#ffffff', relief='flat', bd=0)
        control_frame.grid(row=0, column=0, sticky='nsew', padx=0, pady=(0, 8))
        control_frame.pack_propagate(True)
        header = tk.Frame(control_frame, bg='#2c3e50', height=35)
        header.pack(fill=tk.X, padx=0, pady=(0, 5))
        header.pack_propagate(False)
        tk.Label(header, text='⚙️ CÔNG CỤ TEST', font=('Segoe UI', 11, 'bold'), fg='white', bg='#2c3e50').pack(pady=6)
        sec1 = tk.Frame(control_frame, bg='#f8f9fa', relief='flat')
        sec1.pack(fill=tk.X, padx=12, pady=(0, 4))
        tk.Label(sec1, text='Kiến trúc', font=('Segoe UI', 9, 'bold'), bg='#f8f9fa', fg='#2c3e50').pack(anchor='w', pady=(2, 2))
        tracker_row = tk.Frame(sec1, bg='#f8f9fa')
        tracker_row.pack(fill=tk.X, pady=1)
        tk.Label(tracker_row, text='Tracker:', font=('Segoe UI', 8), bg='#f8f9fa', width=8).pack(side=tk.LEFT)
        self.cb_tracker = ttk.Combobox(tracker_row, state='readonly', width=18, font=('Segoe UI', 8))
        self.cb_tracker.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        sec2 = tk.Frame(control_frame, bg='#f8f9fa', relief='flat')
        sec2.pack(fill=tk.X, padx=12, pady=(0, 4))
        tk.Label(sec2, text='File & Thư mục', font=('Segoe UI', 9, 'bold'), bg='#f8f9fa', fg='#2c3e50').pack(anchor='w', pady=(2, 3))

        def create_file_row_combo(parent, icon, label_text, browse_cmd):
            row = tk.Frame(parent, bg='#f8f9fa')
            row.pack(fill=tk.X, pady=1)
            row.grid_columnconfigure(1, weight=1)
            tk.Label(row, text=f'{icon} {label_text}', font=('Segoe UI', 8), bg='#f8f9fa', fg='#2c3e50', width=12, anchor='w').grid(row=0, column=0, sticky='w', padx=(0, 5))
            combo = ttk.Combobox(row, font=('Segoe UI', 7), width=16, state='readonly')
            combo.grid(row=0, column=1, sticky='ew', padx=(0, 3))
            tk.Button(row, text='...', command=browse_cmd, font=('Segoe UI', 7, 'bold'), width=3, relief='flat', bg='#ecf0f1', fg='#2c3e50').grid(row=0, column=2)
            return combo
        self.model_combo_file = create_file_row_combo(sec2, '', 'Model', self.browse_model_files)
        self.ocr_model_combo = create_file_row_combo(sec2, '', 'Text (OCR)', self.browse_ocr_model_files)
        self.video_combo = create_file_row_combo(sec2, '', 'Video', self.browse_video_files)
        sec3 = tk.Frame(control_frame, bg='#f8f9fa', relief='flat')
        sec3.pack(fill=tk.X, padx=12, pady=(0, 4))
        tk.Label(sec3, text='Tham số', font=('Segoe UI', 9, 'bold'), bg='#f8f9fa', fg='#2c3e50').pack(anchor='w', pady=(2, 3))
        sec3.grid_columnconfigure(1, weight=1)
        row1 = tk.Frame(sec3, bg='#f8f9fa')
        row1.pack(fill=tk.X, pady=1)
        row1.grid_columnconfigure(1, weight=0)
        tk.Label(row1, text='imgsz:', font=('Segoe UI', 8), bg='#f8f9fa', width=8).grid(row=0, column=0, sticky='w')
        self.img_size_entry = tk.Entry(row1, font=('Segoe UI', 8), relief='solid', bd=1, width=7)
        self.img_size_entry.insert(0, '640')
        self.img_size_entry.grid(row=0, column=1, sticky='w', padx=(0, 6))
        tk.Label(row1, text='stride:', font=('Segoe UI', 8), bg='#f8f9fa', width=7).grid(row=0, column=2, sticky='w')
        self.skip_frame_entry = tk.Entry(row1, font=('Segoe UI', 8), relief='solid', bd=1, width=5)
        self.skip_frame_entry.insert(0, '3')
        self.skip_frame_entry.grid(row=0, column=3, sticky='w')
        row2 = tk.Frame(sec3, bg='#f8f9fa')
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text='conf:', font=('Segoe UI', 8), bg='#f8f9fa', width=8).pack(side=tk.LEFT)
        self.conf_scale = tk.Scale(row2, from_=0.0, to=1.0, resolution=0.01, orient=tk.HORIZONTAL, variable=self.conf_val, bg='#f8f9fa', fg='#2c3e50', highlightthickness=0, length=120, showvalue=False)
        self.conf_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        self.conf_entry = tk.Entry(row2, textvariable=self.conf_val, font=('Segoe UI', 8), width=5, relief='solid', bd=1)
        self.conf_entry.pack(side=tk.LEFT)

        def on_conf_entry_change(*args):
            try:
                val = self.conf_val.get()
                if val < 0.0:
                    self.conf_val.set(0.0)
                elif val > 1.0:
                    self.conf_val.set(1.0)
            except (tk.TclError, ValueError):
                pass
        self.conf_val.trace('w', on_conf_entry_change)
        row3 = tk.Frame(sec3, bg='#f8f9fa')
        row3.pack(fill=tk.X, pady=2)
        tk.Checkbutton(row3, text='🔤 OCR', font=('Segoe UI', 8), variable=self.use_ocr_var, bg='#f8f9fa', fg='#2c3e50', selectcolor='#f8f9fa', activebackground='#f8f9fa', activeforeground='#2c3e50').pack(side=tk.LEFT, padx=(0, 10))
        tk.Checkbutton(row3, text='🛣️ Tracking Trace', font=('Segoe UI', 8), variable=self.use_tracking_trace_var, bg='#f8f9fa', fg='#2c3e50', selectcolor='#f8f9fa', activebackground='#f8f9fa', activeforeground='#2c3e50').pack(side=tk.LEFT)
        sec4 = tk.Frame(control_frame, bg='#f8f9fa', relief='flat')
        sec4.pack(fill=tk.X, padx=12, pady=(0, 4))
        tk.Label(sec4, text='🛡️ Thiết lập vùng cấm', font=('Segoe UI', 9, 'bold'), bg='#f8f9fa', fg='#2c3e50').pack(anchor='w', pady=(2, 3))
        row_roi = tk.Frame(sec4, bg='#f8f9fa')
        row_roi.pack(fill=tk.X, pady=2)
        self.use_roi_var = tk.BooleanVar(value=False)
        self.chk_roi = tk.Checkbutton(row_roi, text='Bật Vùng Cấm', variable=self.use_roi_var, font=('Segoe UI', 8), bg='#f8f9fa')
        self.chk_roi.pack(side=tk.LEFT)
        self.btn_draw_roi = tk.Button(row_roi, text='✏️ Vẽ vùng', font=('Segoe UI', 7, 'bold'), bg='#3498db', fg='white', relief='flat', cursor='hand2', padx=6, command=self.toggle_draw_roi)
        self.btn_draw_roi.pack(side=tk.LEFT, padx=5)
        self.btn_clear_roi = tk.Button(row_roi, text='🗑️ Xóa', font=('Segoe UI', 7, 'bold'), bg='#e74c3c', fg='white', relief='flat', cursor='hand2', padx=6, command=self.clear_roi)
        self.btn_clear_roi.pack(side=tk.LEFT)

        self.alert_banner = tk.Label(control_frame, text='', font=('Segoe UI', 9, 'bold'), bg='#f8f9fa', fg='#f8f9fa', pady=2)
        self.alert_banner.pack(fill=tk.X, padx=12)
        self._alert_flash_count = 0
        btn_frame = tk.Frame(control_frame, bg='#ffffff')
        btn_frame.pack(fill=tk.X, padx=12, pady=(4, 8))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)
        btn_frame.grid_columnconfigure(3, weight=1)
        start_btn = tk.Button(btn_frame, text='▶', bg='#27ae60', fg='white', font=('Segoe UI', 11, 'bold'), relief='flat', cursor='hand2', width=3, pady=3, command=self.callbacks['start_process'])
        start_btn.grid(row=0, column=0, sticky='nsew', padx=(0, 2), pady=2)
        self.pause_btn = tk.Button(btn_frame, text='⏸', bg='#f39c12', fg='white', font=('Segoe UI', 11, 'bold'), relief='flat', cursor='hand2', width=3, pady=3, command=self.callbacks.get('toggle_pause', lambda: None))
        self.pause_btn.grid(row=0, column=1, sticky='nsew', padx=2, pady=2)
        stop_btn = tk.Button(btn_frame, text='⏹', bg='#e74c3c', fg='white', font=('Segoe UI', 11, 'bold'), relief='flat', cursor='hand2', width=3, pady=3, command=self.callbacks['stop_process'])
        stop_btn.grid(row=0, column=2, sticky='nsew', padx=2, pady=2)
        reset_btn = tk.Button(btn_frame, text='🔄', bg='#7f8c8d', fg='white', font=('Segoe UI', 11, 'bold'), relief='flat', cursor='hand2', width=3, pady=3, command=self.callbacks.get('reset_video', lambda: None))
        reset_btn.grid(row=0, column=3, sticky='nsew', padx=(2, 0), pady=2)

        def on_btn_enter(btn, color):

            def handler(e):
                btn.config(bg=color)
            return handler

        def on_btn_leave(btn, color):

            def handler(e):
                btn.config(bg=color)
            return handler
        start_btn.bind('<Enter>', on_btn_enter(start_btn, '#229954'))
        start_btn.bind('<Leave>', on_btn_leave(start_btn, '#27ae60'))
        self.pause_btn.bind('<Enter>', on_btn_enter(self.pause_btn, '#e67e22'))
        self.pause_btn.bind('<Leave>', on_btn_leave(self.pause_btn, '#f39c12'))
        stop_btn.bind('<Enter>', on_btn_enter(stop_btn, '#c0392b'))
        stop_btn.bind('<Leave>', on_btn_leave(stop_btn, '#e74c3c'))
        reset_btn.bind('<Enter>', on_btn_enter(reset_btn, '#95a5a6'))
        reset_btn.bind('<Leave>', on_btn_leave(reset_btn, '#7f8c8d'))
        self.detail_frame = tk.Frame(right_panel, bg='#ffffff', relief='flat', bd=0)
        self.detail_frame.grid(row=1, column=0, sticky='nsew', padx=0, pady=0)
        self.detail_frame.pack_propagate(True)
        detail_header = tk.Frame(self.detail_frame, bg='#34495e', height=45)
        detail_header.pack(fill=tk.X, padx=0, pady=(0, 8))
        detail_header.pack_propagate(False)
        tk.Label(detail_header, text='🚢 CHI TIẾT TÀU', font=('Segoe UI', 11, 'bold'), bg='#34495e', fg='white').pack(pady=10)
        self.detail_canvas = tk.Canvas(self.detail_frame, width=340, height=180, bg='#e8e8e8', relief='flat', bd=0)
        self.detail_canvas.pack(pady=(0, 8), fill=tk.BOTH, expand=True, padx=10)
        self.detail_text = tk.Label(self.detail_frame, text='👆 Click vào tàu trên video...', font=('Segoe UI', 9), wraplength=340, justify=tk.LEFT, bg='#ffffff', fg='#555555', pady=8, padx=10)
        self.detail_text.pack(fill=tk.X)

    def browse_model_files(self):
        folder = filedialog.askdirectory(title='Chọn thư mục chứa model')
        if not folder:
            return
        self._model_folder = folder
        model_files = [f for f in os.listdir(folder) if f.lower().endswith('.pt')]
        if model_files:
            self.model_combo_file['values'] = model_files
            self.model_combo_file.current(0)
            selected_file = model_files[0]
            self.model_path.set(os.path.join(folder, selected_file))
        else:
            messagebox.showwarning('Thông báo', 'Không tìm thấy file .pt trong thư mục')
            self.model_combo_file['values'] = []

    def browse_ocr_model_files(self):
        folder = filedialog.askdirectory(title='Chọn thư mục chứa model Text Detection')
        if not folder:
            return
        self._ocr_folder = folder
        ocr_files = [f for f in os.listdir(folder) if f.lower().endswith('.pt')]
        if ocr_files:
            self.ocr_model_combo['values'] = ocr_files
            self.ocr_model_combo.current(0)
            selected_file = ocr_files[0]
            self.ocr_model_path.set(os.path.join(folder, selected_file))
        else:
            messagebox.showwarning('Thông báo', 'Không tìm thấy file .pt trong thư mục')
            self.ocr_model_combo['values'] = []

    def setup_combobox_bindings(self):

        def on_model_selected(event):
            selected = self.model_combo_file.get()
            if selected and self.model_combo_file.cget('values'):
                if hasattr(self, '_model_folder'):
                    self.model_path.set(os.path.join(self._model_folder, selected))

        def on_ocr_selected(event):
            selected = self.ocr_model_combo.get()
            if selected and self.ocr_model_combo.cget('values'):
                if hasattr(self, '_ocr_folder'):
                    self.ocr_model_path.set(os.path.join(self._ocr_folder, selected))

        def on_video_selected(event):
            selected = self.video_combo.get()
            if selected and self.video_combo.cget('values'):
                if hasattr(self, '_video_folder'):
                    self.video_path.set(os.path.join(self._video_folder, selected))

        def on_tracker_selected(event):
            self.on_tracker_selected(event)
        self.model_combo_file.bind('<<ComboboxSelected>>', on_model_selected)
        self.ocr_model_combo.bind('<<ComboboxSelected>>', on_ocr_selected)
        self.video_combo.bind('<<ComboboxSelected>>', on_video_selected)
        self.cb_tracker.bind('<<ComboboxSelected>>', on_tracker_selected)

    def toggle_draw_roi(self):
        self.drawing_roi = not self.drawing_roi
        if self.drawing_roi:
            self.roi_original_points.clear()
            self.roi_closed = False
            self.btn_draw_roi.config(text='❌ Hủy vẽ', bg='#e67e22')
            if self.engine:
                self.engine.roi_polygon = []
            self.show_info('Hướng dẫn', 'Click chuột trái vào video để thêm điểm.\nClick chuột phải để hoàn tất đóng vùng cấm.')
            self.redraw_current_frame()
        else:
            self.btn_draw_roi.config(text='✏️ Vẽ vùng', bg='#3498db')
            self.roi_closed = True
            if self.engine:
                self.engine.roi_polygon = self.roi_original_points
            self.redraw_current_frame()

    def clear_roi(self):
        self.roi_original_points.clear()
        self.roi_closed = False
        self.drawing_roi = False
        self.btn_draw_roi.config(text='✏️ Vẽ vùng', bg='#3498db')
        if self.engine:
            self.engine.roi_polygon = []
        self.redraw_current_frame()
        self.show_info('Thông báo', 'Đã xóa vùng cấm!')



    def show_violation_alert(self, track_id):
        self.alert_banner.config(text=f'⚠️ CẢNH BÁO: Tàu ID {track_id} xâm nhập vùng cấm!')
        self._alert_flash_count = 10
        self._flash_alert()

    def _flash_alert(self):
        if self._alert_flash_count <= 0:
            self.alert_banner.config(bg='#f8f9fa', fg='#f8f9fa')
            return
        if self._alert_flash_count % 2 == 0:
            self.alert_banner.config(bg='#e74c3c', fg='white')
        else:
            self.alert_banner.config(bg='#f39c12', fg='white')
        self._alert_flash_count -= 1
        self.root.after(400, self._flash_alert)

    def canvas_to_original_coords(self, cx, cy):
        if not hasattr(self, 'video_w') or not self.video_w:
            return (cx, cy)
        cw = self.canvas_video.winfo_width()
        ch = self.canvas_video.winfo_height()
        if cw <= 0 or ch <= 0:
            return (cx, cy)
        h, w = (self.video_h, self.video_w)
        base_scale = min(cw / w, ch / h)
        nw, nh = (int(w * base_scale), int(h * base_scale))
        offset_x = (cw - nw) // 2
        offset_y = (ch - nh) // 2
        if self.zoom_level > 1.0:
            view_w = int(nw / self.zoom_level)
            view_h = int(nh / self.zoom_level)
            cxx = nw // 2 + self.pan_x
            cyy = nh // 2 + self.pan_y
            x1_crop = max(0, cxx - view_w // 2)
            y1_crop = max(0, cyy - view_h // 2)
            real_x = cx / cw * view_w + x1_crop
            real_y = cy / ch * view_h + y1_crop
            rx = real_x / base_scale
            ry = real_y / base_scale
        else:
            rx = (cx - offset_x) / base_scale
            ry = (cy - offset_y) / base_scale
        return (rx, ry)

    def original_to_canvas_coords(self, rx, ry):
        if not hasattr(self, 'video_w') or not self.video_w:
            return (rx, ry)
        cw = self.canvas_video.winfo_width()
        ch = self.canvas_video.winfo_height()
        if cw <= 0 or ch <= 0:
            return (rx, ry)
        h, w = (self.video_h, self.video_w)
        base_scale = min(cw / w, ch / h)
        nw, nh = (int(w * base_scale), int(h * base_scale))
        offset_x = (cw - nw) // 2
        offset_y = (ch - nh) // 2
        if self.zoom_level > 1.0:
            view_w = int(nw / self.zoom_level)
            view_h = int(nh / self.zoom_level)
            cxx = nw // 2 + self.pan_x
            cyy = nh // 2 + self.pan_y
            x1_crop = max(0, cxx - view_w // 2)
            y1_crop = max(0, cyy - view_h // 2)
            bx = rx * base_scale
            by = ry * base_scale
            cx = (bx - x1_crop) / view_w * cw
            cy = (by - y1_crop) / view_h * ch
        else:
            cx = rx * base_scale + offset_x
            cy = ry * base_scale + offset_y
        return (cx, cy)

    def redraw_current_frame(self):
        if hasattr(self, 'last_frame') and self.last_frame is not None:
            self.update_frame(self.last_frame, 0)

    def on_canvas_right_click(self, event):
        if self.drawing_roi and len(self.roi_original_points) >= 3:
            self.roi_closed = True
            self.drawing_roi = False
            self.btn_draw_roi.config(text='✏️ Vẽ vùng', bg='#3498db')
            if self.engine:
                self.engine.roi_polygon = self.roi_original_points
            self.redraw_current_frame()
            self.show_info('Thông báo', 'Đã thiết lập vùng cấm thành công!')

    def load_trackers(self):
        try:
            from pathlib import Path
            tracker_dir = Path(__file__).parent.parent / 'trackers'
            if not tracker_dir.exists():
                print(f'⚠️ Thư mục trackers không tìm thấy: {tracker_dir}')
                self.cb_tracker['values'] = ['None']
                self.cb_tracker.set('None')
                return
            yaml_files = sorted(list(tracker_dir.glob('*.yaml')) + list(tracker_dir.glob('*.yml')))
            if not yaml_files:
                print('⚠️ Không có file .yaml hoặc .yml trong thư mục trackers')
                self.cb_tracker['values'] = ['None']
                self.cb_tracker.set('None')
                return
            self.tracker_files = yaml_files
            tracker_names = [f.name for f in yaml_files]
            self.cb_tracker['values'] = tracker_names
            default_tracker_name = tracker_names[0]
            default_tracker_file = yaml_files[0]
            for f in yaml_files:
                if f.name.lower() == 'bytetrack.yml':
                    default_tracker_name = f.name
                    default_tracker_file = f
                    break
            self.cb_tracker.set(default_tracker_name)
            self.tracker_path.set(str(default_tracker_file))
            print(f'✅ Đã load {len(tracker_names)} tracker file: {tracker_names}')
        except Exception as e:
            print(f'❌ Lỗi load tracker files: {e}')
            self.cb_tracker['values'] = ['None']
            self.cb_tracker.set('None')

    def on_tracker_selected(self, event=None):
        selected_name = self.cb_tracker.get()
        if selected_name == 'None' or not self.tracker_files:
            self.tracker_path.set('bytetrack.yml')
            return
        for f in self.tracker_files:
            if f.name == selected_name:
                self.tracker_path.set(str(f))
                break

    def load_default_directories(self):
        from src.utils.path_utils import get_external_root
        project_root = get_external_root()
        models_dir = project_root / 'models'
        if models_dir.exists():
            self._model_folder = str(models_dir)
            self._ocr_folder = str(models_dir)
            model_files = [f for f in os.listdir(models_dir) if f.lower().endswith('.pt') or f.lower().endswith('.engine')]
            if model_files:
                self.model_combo_file['values'] = model_files
                self.ocr_model_combo['values'] = model_files
                default_model = model_files[0]
                for m in model_files:
                    if m.lower() == 'best.pt':
                        default_model = m
                        break
                self.model_combo_file.set(default_model)
                self.model_path.set(str(models_dir / default_model))
                default_ocr_model = model_files[0]
                for m in model_files:
                    if m.lower() == 'best(8).pt':
                        default_ocr_model = m
                        break
                else:
                    for m in model_files:
                        if 'text' in m.lower() or 'ocr' in m.lower():
                            default_ocr_model = m
                            break
                self.ocr_model_combo.set(default_ocr_model)
                self.ocr_model_path.set(str(models_dir / default_ocr_model))
        video_dir = project_root / 'videos'
        if video_dir.exists():
            self._video_folder = str(video_dir)
            video_ext = ('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm')
            video_files = [f for f in os.listdir(video_dir) if f.lower().endswith(video_ext)]
            if video_files:
                self.video_combo['values'] = video_files
                self.video_combo.set(video_files[0])
                self.video_path.set(str(video_dir / video_files[0]))
        output_dir = project_root / 'outputs'
        os.makedirs(output_dir, exist_ok=True)
        self.output_dir.set(str(output_dir))

    def browse_video_files(self):
        folder = filedialog.askdirectory(title='Chọn thư mục chứa video')
        if not folder:
            return
        video_ext = ('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm')
        video_files = [f for f in os.listdir(folder) if f.lower().endswith(video_ext)]
        if video_files:
            self._video_folder = folder
            self.video_combo['values'] = video_files
            self.video_combo.current(0)
            selected_file = video_files[0]
            self.video_path.set(os.path.join(folder, selected_file))
        else:
            messagebox.showwarning('Thông báo', 'Không tìm thấy file video trong thư mục')
            self.video_combo['values'] = []

    def refresh_database_ui(self, rows):
        self.log_view.refresh_database_ui(rows)

    def show_db_info(self, info, img_path):
        self.log_view.show_db_info(info, img_path)

    @property
    def tree(self):
        return self.log_view.tree

    @property
    def ship_history_tree(self):
        return self.log_view.ship_history_tree

    @property
    def refresh_status(self):
        return self.log_view.refresh_status

    @refresh_status.setter
    def refresh_status(self, value):
        self.log_view.refresh_status.config(text=value)

    def update_frame(self, frame, fps):

        def task(frame_copy):
            h, w = frame_copy.shape[:2]
            self.video_w = w
            self.video_h = h
            self.last_frame = frame_copy
            ch, cw = (self.canvas_video.winfo_height(), self.canvas_video.winfo_width())
            if ch <= 0 or cw <= 0:
                return
            base_scale = min(cw / w, ch / h)
            nw, nh = (int(w * base_scale), int(h * base_scale))
            self.last_scale = base_scale
            self.last_offset = ((cw - nw) // 2, (ch - nh) // 2)
            try:
                img = cv2.resize(frame_copy, (nw, nh))
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                if self.zoom_level > 1.0:
                    view_w = int(nw / self.zoom_level)
                    view_h = int(nh / self.zoom_level)
                    max_pan_x = max(0, (nw - view_w) // 2)
                    max_pan_y = max(0, (nh - view_h) // 2)
                    px = max(-max_pan_x, min(max_pan_x, self.pan_x))
                    py = max(-max_pan_y, min(max_pan_y, self.pan_y))
                    self.pan_x, self.pan_y = (px, py)
                    cx = nw // 2 + px
                    cy = nh // 2 + py
                    x1 = max(0, cx - view_w // 2)
                    y1 = max(0, cy - view_h // 2)
                    x2 = min(nw, x1 + view_w)
                    y2 = min(nh, y1 + view_h)
                    zoomed = img[y1:y2, x1:x2]
                    zoomed = cv2.resize(zoomed, (cw, ch))
                    self.tk_img = ImageTk.PhotoImage(image=Image.fromarray(zoomed))
                    self.canvas_video.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
                else:
                    self.tk_img = ImageTk.PhotoImage(image=Image.fromarray(img))
                    self.canvas_video.create_image(cw // 2, ch // 2, anchor=tk.CENTER, image=self.tk_img)
                self.canvas_video.delete('roi')
                if hasattr(self, 'roi_original_points') and self.roi_original_points:
                    canvas_points = []
                    for rx, ry in self.roi_original_points:
                        cx, cy = self.original_to_canvas_coords(rx, ry)
                        canvas_points.append((cx, cy))
                    n = len(canvas_points)
                    for idx in range(n):
                        cx1, cy1 = canvas_points[idx]
                        cx2, cy2 = canvas_points[(idx + 1) % n]
                        if not self.roi_closed and idx == n - 1:
                            break
                        self.canvas_video.create_line(cx1, cy1, cx2, cy2, fill='red', width=2, tags='roi')
                        self.canvas_video.create_oval(cx1 - 4, cy1 - 4, cx1 + 4, cy1 + 4, fill='yellow', outline='red', tags='roi')
            except Exception as e:
                print(f'Lỗi cập nhật frame: {e}')
        self.root.after(0, lambda: task(frame))

    def show_crop(self, img_cv):
        if img_cv is None or img_cv.size == 0:
            return
        img = cv2.resize(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB), (330, 170))
        self.tk_crop = ImageTk.PhotoImage(image=Image.fromarray(img))
        self.detail_canvas.create_image(170, 85, anchor=tk.CENTER, image=self.tk_crop)

    def show_detail_text(self, text):
        self.detail_text.config(text=text)

    def show_warning(self, title, msg):
        messagebox.showwarning(title, msg)

    def show_error(self, title, msg):
        messagebox.showerror(title, msg)

    def show_info(self, title, msg):
        messagebox.showinfo(title, msg)

    def ask_yesno(self, title, msg):
        return messagebox.askyesno(title, msg)

    def _on_zoom(self, event):
        if event.num == 4 or event.delta > 0:
            factor = 1.15
        elif event.num == 5 or event.delta < 0:
            factor = 1 / 1.15
        else:
            return
        new_zoom = self.zoom_level * factor
        new_zoom = max(self.zoom_min, min(self.zoom_max, new_zoom))
        if new_zoom != self.zoom_level:
            cw = self.canvas_video.winfo_width()
            ch = self.canvas_video.winfo_height()
            mx = event.x - cw // 2
            my = event.y - ch // 2
            scale_change = new_zoom / self.zoom_level
            self.pan_x = int(self.pan_x * scale_change + mx * (scale_change - 1) * 0.3)
            self.pan_y = int(self.pan_y * scale_change + my * (scale_change - 1) * 0.3)
            self.zoom_level = new_zoom
        if self.zoom_level <= 1.0:
            self.zoom_level = 1.0
            self.pan_x = 0
            self.pan_y = 0

    def _pan_start_drag(self, event):
        self._pan_start = (event.x, event.y)
        self.canvas_video.config(cursor='fleur')

    def _pan_do_drag(self, event):
        if self._pan_start is None or self.zoom_level <= 1.0:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self.pan_x += dx
        self.pan_y += dy
        self._pan_start = (event.x, event.y)

    def _pan_end_drag(self, event):
        self._pan_start = None
        self.canvas_video.config(cursor='')

    def reset_zoom(self):
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0

    def update_progress(self, current, total):
        if total > 0:
            pct = int(current / total * 100)
            self.progress_bar['value'] = pct
            self.progress_label.config(text=f'Frame: {current} / {total}  ({pct}%)')
        else:
            self.progress_bar['value'] = 0
            self.progress_label.config(text='Frame: 0 / 0  (0%)')
