import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import cv2
import os
from src.utils.sql_logger import get_sql_logger
from datetime import datetime
from pathlib import Path

class LogController:

    def __init__(self, root, view):
        self.root = root
        self.view = view
        self.current_output_folder = 'outputs'

    def set_output_folder(self, folder):
        self.current_output_folder = folder

    def refresh_database(self):
        try:
            sql_logger = get_sql_logger(self.current_output_folder)
            logs = sql_logger.get_all_logs()
            if not logs:
                self.view.refresh_database_ui([])
                self.view.log_view.refresh_status.config(text='✅ Không có dữ liệu')
                return
            if hasattr(self.view.log_view, 'search_var'):
                search_text = self.view.log_view.search_var.get().strip().lower()
                search_type = self.view.log_view.search_type.get()
                if search_text:
                    filtered_logs = []
                    for log in logs:
                        if search_type == 'Số hiệu':
                            val = str(log.get('so_hieu_ocr', 'N/A')).lower()
                            if search_text in val:
                                filtered_logs.append(log)
                        elif search_type == 'Loại tàu':
                            val = str(log.get('class_name', '')).lower()
                            if search_text in val:
                                filtered_logs.append(log)
                    logs = filtered_logs
            rows = []
            for log in logs:
                img_path = log.get('hinh_anh_path', '')
                if isinstance(img_path, float):
                    img_path = ''
                so_hieu = log.get('so_hieu_ocr', 'N/A')
                if isinstance(so_hieu, float):
                    so_hieu = 'N/A'
                row = (log.get('track_id', ''), log.get('class_name', ''), so_hieu, log.get('gio_phat_hien', ''), img_path, log.get('video_source', 'Unknown'), log.get('unique_id', ''), log.get('ghi_chu', '') or '')
                rows.append(row)
            self.view.refresh_database_ui(rows)
            self.view.log_view.refresh_status.config(text='✅ Đã làm mới!')
            self.root.after(2000, lambda: self.view.log_view.refresh_status.config(text=''))
        except Exception as e:
            self.view.show_error('Lỗi', f'Không thể tải dữ liệu:\n{str(e)}')

    def on_tree_select(self, event):
        selected = self.view.log_view.tree.selection()
        if not selected:
            return
        item_id = selected[0]
        values = self.view.log_view.tree.item(item_id, 'values')
        img_path = self.view.log_view.tree_img_paths.get(item_id, '')
        info = f"🆔 ID Tracking : {values[0]}\n🚢 Loại tàu      : {values[1]}\n🔢 Số hiệu (OCR) : {values[2]}\n🕐 Giờ phát hiện : {values[3]}\n📹 Nguồn video   : {(values[4] if len(values) > 4 else 'Unknown')}"
        self.view.show_db_info(info, img_path)

    def load_ship_history(self, so_hieu):
        self.view.log_view.ship_history_tree.delete(*self.view.log_view.ship_history_tree.get_children())
        try:
            sql_logger = get_sql_logger(self.current_output_folder)
            logs = sql_logger.get_logs_by_so_hieu(so_hieu)
            if not logs:
                return
            for log in logs:
                self.view.log_view.ship_history_tree.insert('', tk.END, values=(log.get('gio_phat_hien', ''), log.get('so_hieu_ocr', 'N/A'), log.get('video_source', 'Unknown')))
        except Exception as e:
            print(f'Lỗi load lịch sử tàu: {e}')

    def manual_ocr(self):
        selected = self.view.log_view.tree.selection()
        if not selected:
            messagebox.showwarning('Chưa chọn', 'Vui lòng chọn một tàu trong bảng trước!')
            return
        item_id = selected[0]
        values = self.view.log_view.tree.item(item_id, 'values')
        track_id = int(values[0])
        img_rel_path = self.view.log_view.tree_img_paths.get(item_id, '')
        unique_id = getattr(self.view.log_view, 'tree_unique_ids', {}).get(item_id, '')
        engine = getattr(self.view, 'engine', None)
        if engine and track_id in getattr(engine, 'current_objects', {}):
            if engine.use_ocr and engine.ocr_engine:
                engine.request_manual_ocr(track_id)
                messagebox.showinfo('Đã gửi', f'Đã yêu cầu OCR cho ID {track_id}')
                return
        if img_rel_path:
            if os.path.exists(img_rel_path):
                img_full_path = img_rel_path
            else:
                img_full_path = os.path.join(self.current_output_folder, img_rel_path)
            if os.path.exists(img_full_path):
                self.manual_ocr_from_file(track_id, unique_id, img_full_path)
            else:
                messagebox.showwarning('Cảnh báo', f'Không tìm thấy ảnh:\n{img_full_path}')
        else:
            messagebox.showwarning('Cảnh báo', 'Không có ảnh lưu trữ hoặc hệ thống giám sát chưa chạy.')

    def manual_ocr_from_file(self, track_id, unique_id, img_path):
        try:
            if not os.path.exists(img_path):
                messagebox.showerror('Lỗi', f'Không tìm thấy file ảnh:\n{img_path}')
                return
            crop = cv2.imread(img_path)
            if crop is None:
                messagebox.showerror('Lỗi', 'Không thể đọc file ảnh!')
                return
            messagebox.showinfo('Đang xử lý', 'Đang OCR...')
            engine = getattr(self.view, 'engine', None)
            text, score = (None, 0.0)
            if engine and engine.use_ocr and engine.text_model and engine.ocr_engine:
                print(f'>> Sử dụng 2-Stage OCR (Engine)')
                try:
                    text_results = engine.text_model(crop, conf=0.5, verbose=False)
                    text_crop = None
                    for result in text_results:
                        if result.boxes is None or len(result.boxes) == 0:
                            continue
                        boxes = result.boxes
                        conf_scores = boxes.conf.cpu().numpy()
                        best_idx = conf_scores.argmax()
                        box = boxes.xyxy[best_idx].cpu().numpy().astype(int)
                        x1, y1, x2, y2 = box
                        pad = 5
                        x1 = max(0, x1 - pad)
                        y1 = max(0, y1 - pad)
                        x2 = min(crop.shape[1], x2 + pad)
                        y2 = min(crop.shape[0], y2 + pad)
                        if x2 - x1 >= 10 and y2 - y1 >= 10:
                            text_crop = crop[y1:y2, x1:x2].copy()
                            break
                    if text_crop is None:
                        raise Exception('Stage 1 Failed: Không detect được vùng chữ')
                    results = engine.ocr_engine.ocr_image(text_crop)
                    if results:
                        best = max(results, key=lambda x: x.get('score', 0))
                        text = best['text'].strip().upper()
                        score = best['score']
                    else:
                        raise Exception('Stage 2 Failed: PaddleOCR không đọc được')
                except Exception as e:
                    print(f'>> 2-Stage OCR Error: {e}. Fallback to PaddleOCR...')
                    text, score = (None, 0.0)
            if text is None:
                print(f'>> Sử dụng PaddleOCR (Fallback)')
                from src.engines.ocr_engine import ShipOCR
                ocr = ShipOCR()
                results = ocr.ocr_image(crop)
                if not results:
                    messagebox.showwarning('Kết quả', 'OCR không đọc được ký tự nào.')
                    return
                best = max(results, key=lambda x: x.get('score', 0))
                text = best['text'].strip().upper()
                score = best['score']
            print(f'>> OCR Result [track_id {track_id} | unique_id {unique_id}]: {text} ({score:.1%})')
            sql_logger = get_sql_logger(self.current_output_folder)
            sql_logger.update_log_by_unique_id(unique_id=unique_id, so_hieu_ocr=text, do_tin_cay_ocr=score)
            messagebox.showinfo('Thành công', f'OCR Result: {text}\nĐộ tin cây: {score:.1%}')
            self.refresh_database()
        except Exception as e:
            messagebox.showerror('Lỗi OCR', str(e))

    def edit_ghi_chu(self):
        selected = self.view.log_view.tree.selection()
        if not selected:
            messagebox.showwarning('Chưa chọn', 'Vui lòng chọn một tàu trong bảng trước!')
            return
        item_id = selected[0]
        values = self.view.log_view.tree.item(item_id, 'values')
        unique_id = getattr(self.view.log_view, 'tree_unique_ids', {}).get(item_id, '')
        current_note = values[5] if len(values) > 5 else ''
        if not unique_id:
            messagebox.showwarning('Lỗi', 'Không tìm thấy ID bản ghi!')
            return
        popup = tk.Toplevel(self.root)
        popup.title('✏️ Sửa ghi chú')
        popup.geometry('480x220')
        popup.resizable(False, False)
        popup.grab_set()
        popup.focus_force()
        header = tk.Frame(popup, bg='#2980b9', height=45)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f'✏️ Ghi chú cho tàu ID: {values[0]}', font=('Segoe UI', 11, 'bold'), bg='#2980b9', fg='white').pack(pady=10)
        body = tk.Frame(popup, bg='white', padx=20, pady=10)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text='Nội dung ghi chú:', font=('Segoe UI', 10, 'bold'), bg='white', fg='#2c3e50').pack(anchor='w', pady=(5, 3))
        note_var = tk.StringVar(value=current_note)
        note_entry = tk.Entry(body, textvariable=note_var, font=('Segoe UI', 11), relief='solid', bd=1)
        note_entry.pack(fill=tk.X, ipady=6)
        note_entry.select_range(0, tk.END)
        note_entry.focus_set()
        btn_frame = tk.Frame(body, bg='white')
        btn_frame.pack(pady=12)

        def save_note():
            ghi_chu = note_var.get().strip()
            sql_logger = get_sql_logger(self.current_output_folder)
            if sql_logger.update_ghi_chu(unique_id, ghi_chu):
                popup.destroy()
                self.refresh_database()
                self.view.log_view.refresh_status.config(text='✅ Đã lưu ghi chú!')
                self.root.after(2000, lambda: self.view.log_view.refresh_status.config(text=''))
            else:
                messagebox.showerror('Lỗi', 'Không thể lưu ghi chú. Kiểm tra kết nối CSDL!', parent=popup)
        tk.Button(btn_frame, text='💾 Lưu', bg='#2980b9', fg='white', font=('Segoe UI', 10, 'bold'), padx=20, pady=6, bd=0, cursor='hand2', command=save_note).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text='Hủy', bg='#ecf0f1', fg='#2c3e50', font=('Segoe UI', 10), padx=20, pady=6, bd=0, cursor='hand2', command=popup.destroy).pack(side=tk.LEFT)
        popup.bind('<Return>', lambda e: save_note())
