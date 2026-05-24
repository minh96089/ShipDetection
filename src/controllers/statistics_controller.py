import os
import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from src.utils.sql_logger import get_sql_logger
from src.utils.excel_exporter import export_shiplogs_to_excel

class StatisticsController:

    def __init__(self, view, root):
        self.view = view
        self.root = root
        self.sql_logger = get_sql_logger()
        self.view.callbacks['on_filter_change'] = self.load_and_refresh_data
        self.view.callbacks['on_export_excel'] = self.export_to_excel
        self.all_logs = []
        self.filtered_logs = []
        self.root.after(500, self.initial_load)

    def initial_load(self):
        self.load_all_logs_from_db()
        sources = set((log['video_source'] for log in self.all_logs if log.get('video_source')))
        self.view.populate_source_combobox(sources)
        self.load_and_refresh_data()

    def load_all_logs_from_db(self):
        try:
            self.all_logs = self.sql_logger.get_all_logs()
        except Exception as e:
            print(f'>> StatisticsController Error loading logs: {e}')
            self.all_logs = []

    def load_and_refresh_data(self):
        self.load_all_logs_from_db()
        if not self.all_logs:
            self.draw_empty_charts()
            return
        filters = self.view.get_filter_values()
        df = pd.DataFrame(self.all_logs)
        if filters['source'] and filters['source'] != 'Tất cả':
            df = df[df['video_source'] == filters['source']]
        if filters['start_date']:
            try:
                start_dt = pd.to_datetime(filters['start_date'])
                df = df[pd.to_datetime(df['gio_phat_hien']) >= start_dt]
            except Exception:
                messagebox.showwarning('Lỗi Định Dạng', 'Định dạng ngày bắt đầu không hợp lệ (hãy dùng YYYY-MM-DD)!')
        if filters['end_date']:
            try:
                end_dt = pd.to_datetime(filters['end_date']) + pd.Timedelta(days=1)
                df = df[pd.to_datetime(df['gio_phat_hien']) < end_dt]
            except Exception:
                messagebox.showwarning('Lỗi Định Dạng', 'Định dạng ngày kết thúc không hợp lệ (hãy dùng YYYY-MM-DD)!')
        self.filtered_logs = df.to_dict('records')
        if len(self.filtered_logs) == 0:
            self.draw_empty_charts()
            return
        self.draw_class_chart(df)
        self.draw_density_chart(df)
        self.draw_violations_chart(df)

    def draw_empty_charts(self):
        for tab in ['class', 'density', 'violations']:
            fig = Figure(figsize=(6, 4), dpi=100)
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'Không có dữ liệu phù hợp', horizontalalignment='center', verticalalignment='center', fontsize=12, color='gray')
            ax.axis('off')
            self.view.display_chart(fig, tab)

    def draw_class_chart(self, df):
        class_counts = df['class_name'].value_counts()
        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)
        colors = ['#1abc9c', '#3498db', '#e67e22', '#9b59b6', '#e74c3c']
        bars = ax.bar(class_counts.index, class_counts.values, color=colors[:len(class_counts)], width=0.5)
        ax.set_title('Số Lượng Phát Hiện Theo Loại Tàu', fontsize=11, fontweight='bold', pad=15)
        ax.set_xlabel('Loại Tàu', fontsize=9)
        ax.set_ylabel('Số Lượt Phát Hiện', fontsize=9)
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height}', xy=(bar.get_x() + bar.get_width() / 2, height), xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontsize=8, fontweight='bold')
        fig.subplots_adjust(left=0.12, right=0.95, top=0.88, bottom=0.15)
        self.view.display_chart(fig, 'class')

    def draw_density_chart(self, df):
        df_times = df.copy()
        df_times['date_only'] = pd.to_datetime(df_times['gio_phat_hien']).dt.date
        density = df_times.groupby('date_only').size()
        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(density.index.astype(str), density.values, marker='o', color='#3498db', linewidth=2, markersize=6)
        ax.set_title('Mật Độ Phát Hiện Tàu Theo Thời Gian', fontsize=11, fontweight='bold', pad=15)
        ax.set_xlabel('Ngày Phát Hiện', fontsize=9)
        ax.set_ylabel('Số Lượt Phát Hiện', fontsize=9)
        ax.grid(True, linestyle='--', alpha=0.5)
        fig.autofmt_xdate(rotation=30)
        for i, val in enumerate(density.values):
            ax.annotate(str(val), (str(density.index[i]), val), textcoords='offset points', xytext=(0, 7), ha='center', fontsize=8, color='#2c3e50', fontweight='bold')
        fig.subplots_adjust(left=0.1, right=0.95, top=0.88, bottom=0.22)
        self.view.display_chart(fig, 'density')

    def draw_violations_chart(self, df):
        df_warn = df.copy()
        df_warn['violation'] = df_warn['ghi_chu'].fillna('').apply(lambda x: 'Cảnh Báo Xâm Nhập' if 'CẢNH BÁO' in x else 'Bình Thường')
        counts = df_warn['violation'].value_counts()
        if 'Cảnh Báo Xâm Nhập' not in counts:
            counts['Cảnh Báo Xâm Nhập'] = 0
        if 'Bình Thường' not in counts:
            counts['Bình Thường'] = 0
        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)
        labels = ['Bình Thường', 'Cảnh Báo Xâm Nhập']
        values = [counts['Bình Thường'], counts['Cảnh Báo Xâm Nhập']]
        colors = ['#2ecc71', '#e74c3c']
        total = sum(values)

        def _autopct(pct):
            if pct <= 0 or total <= 0:
                return ''
            return f'{pct:.1f}%\n({int(round(pct * total / 100))})'
        wedges, _texts, autotexts = ax.pie(values, labels=None, autopct=_autopct, startangle=90, colors=colors, textprops=dict(color='#2c3e50', size=9), wedgeprops=dict(width=0.42, edgecolor='white', linewidth=2), pctdistance=0.78)
        for autotext in autotexts:
            autotext.set_fontweight('bold')
            autotext.set_fontsize(9)
            autotext.set_color('white')
        ax.legend(wedges, labels, loc='upper center', bbox_to_anchor=(0.5, -0.02), ncol=2, frameon=False, fontsize=9)
        ax.set_aspect('equal')
        ax.set_title('Tỉ Lệ Tàu Thuyền Vi Phạm Vùng Cấm', fontsize=11, fontweight='bold', pad=12)
        fig.subplots_adjust(left=0.08, right=0.92, top=0.88, bottom=0.18)
        self.view.display_chart(fig, 'violations')

    def export_to_excel(self):
        if not self.filtered_logs:
            messagebox.showwarning('Không Có Dữ Liệu', 'Không có dữ liệu phù hợp với bộ lọc hiện tại để xuất báo cáo!')
            return
        filename = f"report_statistics_{datetime.now().strftime('%Y%md_%H%M%S')}.xlsx"
        filepath = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel Files', '*.xlsx')], initialfile=filename, title='Lưu Báo Cáo Thống Kê')
        if filepath:
            try:
                export_shiplogs_to_excel(self.filtered_logs, filepath)
                messagebox.showinfo('Thành Công', f'Đã xuất báo cáo thống kê thành công!\nĐường dẫn: {filepath}')
            except Exception as e:
                messagebox.showerror('Lỗi Xuất File', f'Đã xảy ra lỗi khi xuất file Excel:\n{e}')
