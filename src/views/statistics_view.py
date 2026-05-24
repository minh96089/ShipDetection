import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class StatisticsView:

    def __init__(self, parent):
        self.frame = tk.Frame(parent, bg='#f8f9fa')
        self.frame.grid(row=0, column=0, sticky='nsew')
        self.callbacks = {'on_filter_change': None, 'on_export_excel': None}
        self._configure_notebook_style()
        self.setup_ui()

    def _configure_notebook_style(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Stats.TNotebook', tabmargins=[4, 4, 4, 0])
        style.configure('Stats.TNotebook.Tab', font=('Segoe UI', 10), padding=[14, 6])

    def get_frame(self):
        return self.frame

    def setup_ui(self):
        header = tk.Frame(self.frame, bg='#1abc9c', height=60)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text='📈 Thống kê & Phân tích Giao thông Đường thủy', font=('Segoe UI', 14, 'bold'), bg='#1abc9c', fg='white').pack(pady=15, padx=20, side=tk.LEFT)
        content = tk.Frame(self.frame, bg='#f8f9fa')
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=15, pady=15)
        sidebar = tk.Frame(content, bg='white', width=250, relief='solid', bd=1)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='🔍 BỘ LỌC DỮ LIỆU', font=('Segoe UI', 10, 'bold'), bg='white', fg='#2c3e50').pack(anchor='w', padx=15, pady=(15, 10))
        tk.Label(sidebar, text='Nguồn video:', font=('Segoe UI', 8), bg='white', fg='#7f8c8d').pack(anchor='w', padx=15)
        self.combo_source = ttk.Combobox(sidebar, font=('Segoe UI', 9), state='readonly')
        self.combo_source.pack(fill=tk.X, padx=15, pady=(2, 10))
        from tkcalendar import DateEntry
        import datetime
        now = datetime.datetime.now()
        start_default = now - datetime.timedelta(days=30)
        tk.Label(sidebar, text='Từ ngày:', font=('Segoe UI', 8), bg='white', fg='#7f8c8d').pack(anchor='w', padx=15)
        self.entry_start_date = DateEntry(sidebar, font=('Segoe UI', 9), background='#1abc9c', foreground='white', borderwidth=1, date_pattern='yyyy-mm-dd', year=start_default.year, month=start_default.month, day=start_default.day)
        self.entry_start_date.pack(fill=tk.X, padx=15, pady=(2, 10))
        tk.Label(sidebar, text='Đến ngày:', font=('Segoe UI', 8), bg='white', fg='#7f8c8d').pack(anchor='w', padx=15)
        self.entry_end_date = DateEntry(sidebar, font=('Segoe UI', 9), background='#1abc9c', foreground='white', borderwidth=1, date_pattern='yyyy-mm-dd', year=now.year, month=now.month, day=now.day)
        self.entry_end_date.pack(fill=tk.X, padx=15, pady=(2, 15))
        btn_filter = tk.Button(sidebar, text='⚡ Áp dụng bộ lọc', font=('Segoe UI', 9, 'bold'), bg='#3498db', fg='white', relief='flat', cursor='hand2', pady=6, command=self._on_filter_click)
        btn_filter.pack(fill=tk.X, padx=15, pady=(0, 20))
        tk.Frame(sidebar, height=1, bg='#bdc3c7').pack(fill=tk.X, padx=15, pady=10)
        tk.Label(sidebar, text='📤 XUẤT BÁO CÁO', font=('Segoe UI', 10, 'bold'), bg='white', fg='#2c3e50').pack(anchor='w', padx=15, pady=(10, 10))
        btn_export = tk.Button(sidebar, text='📥 Xuất báo cáo Excel', font=('Segoe UI', 9, 'bold'), bg='#27ae60', fg='white', relief='flat', cursor='hand2', pady=8, command=self._on_export_click)
        btn_export.pack(fill=tk.X, padx=15)
        right_panel = tk.Frame(content, bg='white', relief='solid', bd=1)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.notebook = ttk.Notebook(right_panel, style='Stats.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.tab_class = tk.Frame(self.notebook, bg='white')
        self.notebook.add(self.tab_class, text='Phân loại tàu')
        self.tab_density = tk.Frame(self.notebook, bg='white')
        self.notebook.add(self.tab_density, text='Mật độ hoạt động')
        self.tab_violations = tk.Frame(self.notebook, bg='white')
        self.notebook.add(self.tab_violations, text='Xâm nhập vùng cấm')
        self.chart_canvases = {}

    def populate_source_combobox(self, sources):
        list_sources = ['Tất cả'] + list(sources)
        self.combo_source['values'] = list_sources
        self.combo_source.current(0)

    def get_filter_values(self):
        return {'source': self.combo_source.get(), 'start_date': self.entry_start_date.get(), 'end_date': self.entry_end_date.get()}

    def _on_filter_click(self):
        if self.callbacks['on_filter_change']:
            self.callbacks['on_filter_change']()

    def _on_export_click(self):
        if self.callbacks['on_export_excel']:
            self.callbacks['on_export_excel']()

    def display_chart(self, fig, tab_name):
        parent_tab = None
        if tab_name == 'class':
            parent_tab = self.tab_class
        elif tab_name == 'density':
            parent_tab = self.tab_density
        elif tab_name == 'violations':
            parent_tab = self.tab_violations
        if not parent_tab:
            return
        for child in parent_tab.winfo_children():
            child.destroy()
        self.chart_canvases.pop(tab_name, None)
        chart_host = tk.Frame(parent_tab, bg='white')
        chart_host.pack(fill=tk.BOTH, expand=True)
        chart_host.grid_rowconfigure(0, weight=1)
        chart_host.grid_columnconfigure(0, weight=1)
        canvas = FigureCanvasTkAgg(fig, master=chart_host)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew', padx=8, pady=8)
        self.chart_canvases[tab_name] = canvas
