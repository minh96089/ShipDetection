import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

class AlertsView:

    def __init__(self, parent_frame):
        self.parent = parent_frame
        self.page = tk.Frame(parent_frame, bg='#f8f9fa')
        self.page.grid(row=0, column=0, sticky='nsew')
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)
        self.on_refresh_alerts = None
        self.on_mark_reviewed = None
        self.on_mark_resolved = None
        self.on_add_note = None
        self._configure_tree_style()
        self.setup_ui()
        self.alerts_data = []

    def _configure_tree_style(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Alerts.Treeview', background='white', foreground='#2c3e50', rowheight=28, fieldbackground='white', font=('Segoe UI', 10))
        style.configure('Alerts.Treeview.Heading', background='#ebf2f6', foreground='#2c3e50', font=('Segoe UI', 10, 'bold'), relief='flat')
        style.map('Alerts.Treeview', background=[('selected', '#3498db')])

    def get_frame(self):
        return self.page

    def setup_ui(self):
        header_frame = tk.Frame(self.page, bg='#ecf0f1', relief='solid', bd=1)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        title_label = tk.Label(header_frame, text='🚨 Quản lý Cảnh báo Xâm nhập Vùng cấm', font=('Segoe UI', 12, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        title_label.pack(anchor='w', padx=10, pady=10)
        filter_frame = tk.Frame(self.page, bg='#f8f9fa')
        filter_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(filter_frame, text='Lọc:', bg='#f8f9fa', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar(value='all')
        filters = [('Tất cả', 'all'), ('🆕 Mới', 'new'), ('👀 Đã xem', 'reviewed'), ('✅ Đã xử lý xong', 'resolved')]
        for text, value in filters:
            rb = tk.Radiobutton(filter_frame, text=text, variable=self.filter_var, value=value, bg='#f8f9fa', font=('Segoe UI', 9), command=self.on_filter_changed)
            rb.pack(side=tk.LEFT, padx=5)
        tk.Button(filter_frame, text='🔄 Làm mới', font=('Segoe UI', 9), bg='#3498db', fg='white', relief='flat', cursor='hand2', command=self.refresh_alerts).pack(side=tk.RIGHT, padx=5)
        stats_frame = tk.Frame(self.page, bg='#ecf0f1')
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        self.stats_label = tk.Label(stats_frame, text='Tổng: 0 | Mới: 0 | Đã xem: 0 | Đã xử lý xong: 0', bg='#ecf0f1', fg='#34495e', font=('Segoe UI', 9))
        self.stats_label.pack(anchor='w', padx=10, pady=5)
        tree_frame = tk.Frame(self.page, bg='#f8f9fa')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 6))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        vsb = ttk.Scrollbar(tree_frame, orient='vertical')
        self.alerts_tree = ttk.Treeview(tree_frame, columns=('ID', 'Status', 'Tàu ID', 'Loại', 'Thời gian', 'Người xử lý'), show='headings', height=12, style='Alerts.Treeview', yscrollcommand=vsb.set)
        vsb.config(command=self.alerts_tree.yview)
        self._tree_col_specs = [('ID', 'ID', 50, 0.07), ('Status', 'Trạng thái', 140, 0.24), ('Tàu ID', 'Track ID', 70, 0.1), ('Loại', 'Loại tàu', 110, 0.18), ('Thời gian', 'Thời gian', 155, 0.27), ('Người xử lý', 'Xử lý bởi', 90, 0.14)]
        for col_id, heading, min_w, _ratio in self._tree_col_specs:
            self.alerts_tree.heading(col_id, text=heading, anchor=tk.CENTER)
            self.alerts_tree.column(col_id, width=min_w, minwidth=min_w, anchor=tk.CENTER, stretch=False)
        self.alerts_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        self.alerts_tree.bind('<Configure>', self._resize_tree_columns)
        self.page.after_idle(self._resize_tree_columns)
        self.alerts_tree.bind('<Double-1>', self.on_alert_double_click)
        self.alerts_tree.bind('<<TreeviewSelect>>', self.on_alert_selected)
        self.alerts_tree.bind('<Button-3>', self.show_context_menu)
        detail_frame = tk.Frame(self.page, bg='#f8f9fa', relief='solid', bd=1)
        detail_frame.pack(fill=tk.X, padx=10, pady=(4, 8))
        tk.Label(detail_frame, text='Chi tiết cảnh báo:', bg='#f8f9fa', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=10, pady=(5, 0))
        self.detail_text = tk.Text(detail_frame, height=3, width=80, font=('Segoe UI', 9), bg='white', fg='#2c3e50', relief='solid', bd=1)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.detail_text.config(state='disabled')
        action_frame = tk.Frame(self.page, bg='#f8f9fa')
        action_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(action_frame, text='👀 Đánh dấu là Đã xem', font=('Segoe UI', 9), bg='#f39c12', fg='white', relief='flat', cursor='hand2', command=self.mark_as_reviewed).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text='✅ Đã xử lý xong', font=('Segoe UI', 9), bg='#27ae60', fg='white', relief='flat', cursor='hand2', command=self.mark_as_resolved).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text='📝 Thêm ghi chú', font=('Segoe UI', 9), bg='#8e44ad', fg='white', relief='flat', cursor='hand2', command=self.add_note).pack(side=tk.LEFT, padx=5)

    def _resize_tree_columns(self, event=None):
        tree = self.alerts_tree
        if event is not None and event.widget is not tree:
            return
        width = tree.winfo_width()
        if width <= 2:
            return
        total_min = sum((spec[2] for spec in self._tree_col_specs))
        extra = max(0, width - total_min - 6)
        for col_id, _heading, min_w, ratio in self._tree_col_specs:
            col_w = min_w + int(extra * ratio)
            tree.column(col_id, width=col_w, minwidth=min_w, stretch=False)

    def _format_alert_time(self, value):
        if value is None or value == '':
            return ''
        if isinstance(value, datetime):
            return value.strftime('%d/%m/%Y %H:%M:%S')
        text = str(value).strip()
        if '.' in text:
            text = text.split('.', 1)[0]
        for fmt in ('%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S'):
            try:
                return datetime.strptime(text, fmt).strftime('%d/%m/%Y %H:%M:%S')
            except ValueError:
                continue
        return text[:19] if len(text) > 19 else text

    def set_alerts_data(self, alerts_list):
        self.alerts_data = alerts_list
        self.refresh_tree()

    def refresh_tree(self):
        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)
        status_filter = self.filter_var.get()
        for alert in self.alerts_data:
            if status_filter != 'all' and alert.get('status') != status_filter:
                continue
            status = alert.get('status', 'new')
            status_display = {'new': '🆕 Mới', 'reviewed': '👀 Đã xem', 'resolved': '✅ Đã xử lý xong'}.get(status, status)
            handled = alert.get('handled_by')
            handled_display = str(handled) if handled not in (None, '') else 'Chưa xử lý'
            self.alerts_tree.insert('', 'end', values=(alert.get('alert_id', ''), status_display, alert.get('track_id', ''), alert.get('loai_tau') or 'N/A', self._format_alert_time(alert.get('alert_time')), handled_display))

    def on_filter_changed(self):
        self.refresh_tree()

    def refresh_alerts(self, callback=None):
        refresh_callback = callback or self.on_refresh_alerts
        if refresh_callback:
            refresh_callback()

    def on_alert_double_click(self, event):
        selection = self.alerts_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        values = self.alerts_tree.item(item_id, 'values')
        if values:
            alert_id = values[0]
            for alert in self.alerts_data:
                if str(alert.get('alert_id')) == str(alert_id):
                    self.show_alert_detail(alert)
                    break

    def get_selected_alert_id(self):
        selection = self.alerts_tree.selection()
        if not selection:
            return None
        item_id = selection[0]
        values = self.alerts_tree.item(item_id, 'values')
        return values[0] if values else None

    def on_alert_selected(self, event=None):
        alert_id = self.get_selected_alert_id()
        if alert_id is None:
            return
        for alert in self.alerts_data:
            if str(alert.get('alert_id')) == str(alert_id):
                self.show_alert_detail(alert)
                break

    def show_alert_detail(self, alert):
        detail_text = f"ID: {alert.get('alert_id')} | Track ID: {alert.get('track_id')} | Tàu: {alert.get('so_hieu') or 'N/A'} | Loại: {alert.get('loai_tau')}\nThời gian: {self._format_alert_time(alert.get('alert_time'))} | Trạng thái: {alert.get('status')} | Xử lý bởi: {alert.get('handled_by') or 'Chưa xử lý'}\nGhi chú: {alert.get('note') or 'Không có ghi chú'}"
        self.detail_text.config(state='normal')
        self.detail_text.delete('1.0', tk.END)
        self.detail_text.insert('1.0', detail_text)
        self.detail_text.config(state='disabled')

    def show_context_menu(self, event):
        item_id = self.alerts_tree.identify_row(event.y)
        if not item_id:
            return
        self.alerts_tree.selection_set(item_id)
        self.on_alert_double_click(event)
        menu = tk.Menu(self.page, tearoff=0)
        menu.add_command(label='👀 Đánh dấu là Đã xem', command=self.mark_as_reviewed)
        menu.add_command(label='✅ Đã xử lý xong', command=self.mark_as_resolved)
        menu.add_separator()
        menu.add_command(label='📝 Thêm ghi chú', command=self.add_note)
        menu.post(event.x_root, event.y_root)

    def mark_as_reviewed(self, callback=None):
        alert_id = self.get_selected_alert_id()
        if alert_id is None:
            messagebox.showwarning('Canh bao', 'Vui long chon mot canh bao!')
            return
        callback = callback or self.on_mark_reviewed
        if callback:
            callback('reviewed', alert_id)
        return
        'Đánh dấu cảnh báo là đã xem'
        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showwarning('Cảnh báo', 'Vui lòng chọn một cảnh báo!')
            return
        if callback:
            item_id = selection[0]
            values = self.alerts_tree.item(item_id, 'values')
            alert_id = values[0]
            callback('reviewed', alert_id)

    def mark_as_resolved(self, callback=None):
        alert_id = self.get_selected_alert_id()
        if alert_id is None:
            messagebox.showwarning('Canh bao', 'Vui long chon mot canh bao!')
            return
        callback = callback or self.on_mark_resolved
        if callback:
            callback('resolved', alert_id)
        return
        'Đánh dấu cảnh báo là đã xử lý'
        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showwarning('Cảnh báo', 'Vui lòng chọn một cảnh báo!')
            return
        if callback:
            item_id = selection[0]
            values = self.alerts_tree.item(item_id, 'values')
            alert_id = values[0]
            callback('resolved', alert_id)

    def add_note(self, callback=None):
        alert_id = self.get_selected_alert_id()
        if alert_id is None:
            messagebox.showwarning('Canh bao', 'Vui long chon mot canh bao!')
            return
        callback = callback or self.on_add_note
        'Thêm ghi chú cho cảnh báo'
        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showwarning('Cảnh báo', 'Vui lòng chọn một cảnh báo!')
            return
        note_window = tk.Toplevel(self.page)
        note_window.title('Thêm ghi chú')
        note_window.geometry('400x200')
        tk.Label(note_window, text='Ghi chú xử lý:', font=('Segoe UI', 10)).pack(anchor='w', padx=10, pady=(10, 5))
        note_text = tk.Text(note_window, height=5, width=50, font=('Segoe UI', 9))
        note_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def save_note():
            note_content = note_text.get('1.0', tk.END).strip()
            if not note_content:
                messagebox.showwarning('Cảnh báo', 'Vui lòng nhập ghi chú!')
                return
            item_id = selection[0]
            values = self.alerts_tree.item(item_id, 'values')
            alert_id = values[0]
            if callback:
                callback(note_content, alert_id)
            note_window.destroy()
        tk.Button(note_window, text='Lưu', font=('Segoe UI', 9), bg='#27ae60', fg='white', relief='flat', cursor='hand2', command=save_note).pack(pady=10)
