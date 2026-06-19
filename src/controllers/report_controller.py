import os
from pathlib import Path
import tkinter as tk

class ReportController:

    def __init__(self, view, root):
        self.view = view
        self.root = root
        from src.utils.path_utils import get_external_root
        self.project_root = get_external_root()
        self.output_dir = os.path.join(self.project_root, 'outputs')
        self.view.refresh_btn.config(command=self.load_reports)
        self.view.report_listbox.bind('<<ListboxSelect>>', self.on_report_selected)
        self.report_files = []
        self.load_reports()

    def load_reports(self):
        self.view.report_listbox.delete(0, tk.END)
        self.report_files.clear()
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            return
        files = []
        for f in os.listdir(self.output_dir):
            if f.endswith('_REPORT.txt'):
                filepath = os.path.join(self.output_dir, f)
                files.append((f, os.path.getmtime(filepath), filepath))
        files.sort(key=lambda x: x[1], reverse=True)
        for f_name, _, f_path in files:
            self.view.report_listbox.insert(tk.END, f_name)
            self.report_files.append(f_path)

    def on_report_selected(self, event):
        selection = self.view.report_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        filepath = self.report_files[index]
        self.show_report_content(filepath)

    def show_report_content(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.view.text_content.config(state='normal')
            self.view.text_content.delete('1.0', tk.END)
            self.view.text_content.insert('1.0', content)
            self.view.text_content.config(state='disabled')
        except Exception as e:
            self.view.text_content.config(state='normal')
            self.view.text_content.delete('1.0', tk.END)
            self.view.text_content.insert('1.0', f'Lỗi không thể đọc file:\n{e}')
            self.view.text_content.config(state='disabled')

    def open_specific_report(self, filepath):
        self.load_reports()
        for i, path in enumerate(self.report_files):
            if os.path.normpath(path) == os.path.normpath(filepath):
                self.view.report_listbox.selection_clear(0, tk.END)
                self.view.report_listbox.selection_set(i)
                self.view.report_listbox.see(i)
                self.show_report_content(path)
                break
