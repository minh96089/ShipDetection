import tkinter as tk
from tkinter import ttk

class ReportView:

    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.colors = {'bg': '#f4f7f6', 'header': '#ffffff', 'primary': '#3498db', 'text': '#2c3e50'}
        self.frame = tk.Frame(parent_frame, bg=self.colors['bg'])
        self.frame.grid(row=0, column=0, sticky='nsew')
        self.setup_ui()

    def setup_ui(self):
        header_frame = tk.Frame(self.frame, bg=self.colors['header'], height=70)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)
        line = tk.Frame(self.frame, bg='#e0e0e0', height=1)
        line.pack(fill=tk.X)
        tk.Label(header_frame, text='📊 DANH SÁCH BÁO CÁO PHÂN TÍCH', font=('Segoe UI', 16, 'bold'), bg=self.colors['header'], fg=self.colors['text']).pack(side=tk.LEFT, padx=30)
        self.refresh_btn = tk.Button(header_frame, text='🔄 Làm mới', bg=self.colors['primary'], fg='white', font=('Arial', 11, 'bold'), padx=15, pady=5, relief='flat', cursor='hand2')
        self.refresh_btn.pack(side=tk.RIGHT, padx=30)
        main_container = tk.Frame(self.frame, bg=self.colors['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        left_panel = tk.Frame(main_container, bg='white', width=250, bd=1, relief='solid')
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)
        tk.Label(left_panel, text='📁 Tệp Báo Cáo', font=('Segoe UI', 11, 'bold'), bg='#ebf2f6', pady=10).pack(fill=tk.X)
        list_frame = tk.Frame(left_panel, bg='white')
        list_frame.pack(fill=tk.BOTH, expand=True)
        scrollbar_y = tk.Scrollbar(list_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.report_listbox = tk.Listbox(list_frame, font=('Segoe UI', 10), selectbackground=self.colors['primary'], yscrollcommand=scrollbar_y.set, bd=0, highlightthickness=0)
        self.report_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar_y.config(command=self.report_listbox.yview)
        right_panel = tk.Frame(main_container, bg='white', bd=1, relief='solid')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(20, 0))
        tk.Label(right_panel, text='📄 Nội dung chi tiết', font=('Segoe UI', 11, 'bold'), bg='#ebf2f6', pady=10).pack(fill=tk.X)
        text_frame = tk.Frame(right_panel, bg='white')
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_scroll = tk.Scrollbar(text_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_content = tk.Text(text_frame, font=('Consolas', 10), wrap='word', yscrollcommand=text_scroll.set, bd=0, state='disabled')
        self.text_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scroll.config(command=self.text_content.yview)

    def get_frame(self):
        return self.frame
