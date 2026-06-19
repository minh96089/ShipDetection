import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from src.views.main_view import MainView
from src.controllers.log_controller import LogController
from src.controllers.ship_controller import ShipController
from src.controllers.report_controller import ReportController
from src.controllers.alerts_view_controller import AlertsViewController
from src.controllers.auth_controller import CurrentUser, AuthController, Permission
import threading
import os
import cv2
from src.engines.yolo_engine import YoloTester
CLASS_OPTIONS = ['speed boat', 'passenger ship', 'fishing boat']

class MainController:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('AI Ship Detection System')
        self.engine = None
        self.thread = None
        self.selected_track_id = None
        self.callbacks = {'choose_model': self.choose_model, 'choose_video': self.choose_video, 'start_process': self.start_process, 'stop_process': self.stop_process, 'toggle_pause': self.toggle_pause, 'reset_video': self.reset_video, 'refresh_current_page': self.refresh_current_page, 'refresh_database': None, 'on_canvas_click': self.on_canvas_click, 'on_tree_select': None, 'manual_ocr': None, 'edit_ghi_chu': None, 'on_closing': self.on_closing}
        self._progress_poll_id = None
        self.view = MainView(self.root, self.callbacks)
        self.log_controller = LogController(self.root, self.view)
        self.ship_controller = ShipController(self.view.ship_view, self.root, CLASS_OPTIONS)
        self.report_controller = ReportController(self.view.report_view, self.root)
        from src.controllers.statistics_controller import StatisticsController
        self.statistics_controller = StatisticsController(self.view.statistics_view, self.root)
        self.alerts_view_controller = AlertsViewController(self.view.alerts_view, self.root)
        self.callbacks['refresh_database'] = self.log_controller.refresh_database
        self.callbacks['on_tree_select'] = self.log_controller.on_tree_select
        self.callbacks['manual_ocr'] = self.log_controller.manual_ocr
        self.callbacks['edit_ghi_chu'] = self.log_controller.edit_ghi_chu
        self.callbacks['refresh_ships'] = self.ship_controller.refresh_ship_list
        self.view.alerts_view.on_mark_reviewed = self.alerts_view_controller.on_mark_reviewed
        self.view.alerts_view.on_mark_resolved = self.alerts_view_controller.on_mark_resolved
        self.view.alerts_view.on_add_note = self.alerts_view_controller.on_add_note
        self.view.log_view.tree.bind('<<TreeviewSelect>>', self.callbacks['on_tree_select'])
        self.view.log_view.refresh_button.config(command=self.callbacks['refresh_database'])
        self.view.log_view.manual_ocr_btn.config(command=self.callbacks['manual_ocr'])
        self.view.log_view.edit_ghi_chu_btn.config(command=self.callbacks['edit_ghi_chu'])

        def refresh_all(event=None):
            self.callbacks['refresh_database']()
        self.root.bind('<F5>', refresh_all)

    def choose_model(self):
        p = filedialog.askopenfilename(filetypes=[('Model', '*.pt *.engine')])
        if p:
            self.view.model_path.set(p)

    def choose_video(self):
        p = filedialog.askopenfilename(filetypes=[('Video', '*.mp4 *.avi')])
        if p:
            self.view.video_path.set(p)

    def start_process(self):
        if not AuthController.has_permission(Permission.RUN_DETECTION):
            self.view.show_error('Quyền hạn chế', 'Bạn không có quyền chạy phát hiện. Liên hệ quản trị viên.')
            return
        input_source = self.view.video_path.get()
        if not input_source:
            self.view.show_warning('Thiếu thông tin', 'Vui lòng chọn Video File!')
            return
        if not self.view.model_path.get() or not self.view.output_dir.get():
            self.view.show_warning('Thiếu thông tin', 'Vui lòng chọn Model và Output!')
            return
        # Model 4-class tích hợp class Text — không cần text_model_path riêng
        # if self.view.use_ocr_var.get() and (not self.view.ocr_model_path.get()):
        #     self.view.show_warning('Thiếu thông tin', 'Bạn phải chọn Model Text (OCR) nếu bật chế độ OCR!')
        #     return
        try:
            img_sz = int(self.view.img_size_entry.get())
            skp = int(self.view.skip_frame_entry.get())
        except ValueError:
            self.view.show_error('Lỗi', 'Image Size và Skip Frame phải là số nguyên!')
            return
        # Tự động làm tròn imgsz lên bội số 32 (yêu cầu của YOLO stride)
        stride_32 = 32
        img_sz_rounded = ((img_sz + stride_32 - 1) // stride_32) * stride_32
        if img_sz_rounded != img_sz:
            print(f'>> imgsz {img_sz} → làm tròn lên {img_sz_rounded} (bội số 32)')
            img_sz = img_sz_rounded
            self.view.img_size_entry.config(state='normal')
            self.view.img_size_entry.delete(0, 'end')
            self.view.img_size_entry.insert(0, str(img_sz))
            self.view.img_size_entry.config(state='disabled')
        self.selected_track_id = None
        os.makedirs(self.view.output_dir.get(), exist_ok=True)
        self.engine = YoloTester(
            model_path=self.view.model_path.get(),
            input_source=input_source,
            output_folder=self.view.output_dir.get(),
            conf=self.view.conf_val.get(),
            imgsz=img_sz,
            stride=skp,
            use_ocr=self.view.use_ocr_var.get(),
            # text_model_path không cần nữa — model 4-class có class Text tích hợp
            text_model_path=None,
            tracker=self.view.tracker_path.get(),
            use_tracking_trace=self.view.use_tracking_trace_var.get(),
            use_roi=self.view.use_roi_var.get(),
            roi_polygon=self.view.roi_original_points if self.view.use_roi_var.get() else None
        )
        self.view.engine = self.engine
        self.engine.on_violation_alert = self._on_violation_alert
        self.engine.on_ocr_result = self._on_ocr_result_for_detail
        # Khôi phục vùng OCR priority nếu người dùng đã kéo trước đó
        if self.view.ocr_original_region is not None:
            self.engine.ocr_priority_region = self.view.ocr_original_region
            print(f'>> 🎯 Restored OCR priority region: {self.view.ocr_original_region}')

        self.log_controller.set_output_folder(self.view.output_dir.get())
        self.view.img_size_entry.config(state='disabled')
        self.view.skip_frame_entry.config(state='disabled')
        self.view.conf_scale.config(state='disabled')
        self.view.conf_entry.config(state='disabled')
        self.thread = threading.Thread(target=self.engine.run, args=(self.view.update_frame, self.on_report_done))
        self.thread.daemon = True
        self.thread.start()
        self._start_progress_polling()

    def on_report_done(self, txt_path):
        self.view.img_size_entry.config(state='normal')
        self.view.skip_frame_entry.config(state='normal')
        self.view.conf_scale.config(state='normal')
        self.view.conf_entry.config(state='normal')

        def _show():
            self.report_controller.open_specific_report(txt_path)
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                content = f'Không thể đọc file báo cáo:\n{txt_path}'
            popup = tk.Toplevel(self.root)
            popup.title('✅ Hoàn thành - Báo cáo phân tích')
            popup.geometry('680x500')
            popup.resizable(True, True)
            popup.grab_set()
            popup.focus_force()
            header = tk.Frame(popup, bg='#27ae60', height=60)
            header.pack(fill=tk.X)
            header.pack_propagate(False)
            tk.Label(header, text='✅  Xử lý video hoàn tất!', font=('Segoe UI', 14, 'bold'), bg='#27ae60', fg='white').pack(pady=15)
            text_frame = tk.Frame(popup, bg='white')
            text_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            scroll = tk.Scrollbar(text_frame)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            txt = tk.Text(text_frame, font=('Consolas', 10), wrap='word', yscrollcommand=scroll.set, bd=0, bg='#f8f9fa')
            txt.pack(fill=tk.BOTH, expand=True)
            txt.insert('1.0', content)
            txt.config(state='disabled')
            scroll.config(command=txt.yview)
            btn_frame = tk.Frame(popup, bg='white')
            btn_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
            tk.Button(btn_frame, text='📄 Xem tại tab Báo cáo', font=('Segoe UI', 10, 'bold'), bg='#3498db', fg='white', bd=0, padx=20, pady=8, cursor='hand2', command=lambda: [popup.destroy(), self.view.show_frame('reports')]).pack(side=tk.LEFT)
            tk.Button(btn_frame, text='Đóng', font=('Segoe UI', 10), bg='#ecf0f1', fg='#2c3e50', bd=0, padx=20, pady=8, cursor='hand2', command=popup.destroy).pack(side=tk.RIGHT)
        self.root.after(200, _show)

    def _on_violation_alert(self, track_id):
        self.root.after(0, lambda: self.view.show_violation_alert(track_id))

    def toggle_pause(self):
        if not self.engine:
            return
        state = self.engine.toggle_pause()
        if state == 'paused':
            self.view.pause_btn.config(text='▶▮', bg='#8e44ad')
        else:
            self.view.pause_btn.config(text='⏸', bg='#f39c12')

    def stop_process(self):
        if self.engine:
            self.engine.stop()
        self.view.pause_btn.config(text='⏸', bg='#f39c12')
        self._stop_progress_polling()
        self.view.update_progress(0, 0)
        self.view.img_size_entry.config(state='normal')
        self.view.skip_frame_entry.config(state='normal')
        self.view.conf_scale.config(state='normal')
        self.view.conf_entry.config(state='normal')

    def reset_video(self):
        if self.engine:
            self.engine.stop()
            self.engine = None
            self.view.engine = None
        self.view.pause_btn.config(text='⏸', bg='#f39c12')
        self._stop_progress_polling()
        self.view.canvas_video.delete('all')
        self.view.last_frame = None
        self.view.update_progress(0, 0)
        self.view.img_size_entry.config(state='normal')
        self.view.skip_frame_entry.config(state='normal')
        self.view.conf_scale.config(state='normal')
        self.view.conf_entry.config(state='normal')

    def refresh_current_page(self):
        for name, frame in self.view.frames.items():
            if frame.winfo_ismapped():
                if name == 'database':
                    self.callbacks['refresh_database']()
                break

    def on_canvas_click(self, event):
        if self.view.drawing_roi:
            rx, ry = self.view.canvas_to_original_coords(event.x, event.y)
            self.view.roi_original_points.append((rx, ry))
            self.view.redraw_current_frame()
            return
        if not self.engine or not hasattr(self.view, 'last_scale'):
            return
        cw = self.view.canvas_video.winfo_width()
        ch = self.view.canvas_video.winfo_height()
        đang_zoom = self.view.zoom_level > 1.0
        if đang_zoom:
            nw = int(self.view.last_scale * self.view.canvas_video.winfo_width() / self.view.zoom_level * self.view.zoom_level)
            nh = int(self.view.last_scale * self.view.canvas_video.winfo_height() / self.view.zoom_level * self.view.zoom_level)
            base_nw = int(cw * self.view.last_scale)
            base_nh = int(ch * self.view.last_scale)
            view_w = int(base_nw / self.view.zoom_level)
            view_h = int(base_nh / self.view.zoom_level)
            cx = base_nw // 2 + self.view.pan_x
            cy = base_nh // 2 + self.view.pan_y
            x1_crop = max(0, cx - view_w // 2)
            y1_crop = max(0, cy - view_h // 2)
            real_x = event.x / cw * view_w + x1_crop
            real_y = event.y / ch * view_h + y1_crop
            x_click = real_x / self.view.last_scale
            y_click = real_y / self.view.last_scale
        else:
            x_click = (event.x - self.view.last_offset[0]) / self.view.last_scale
            y_click = (event.y - self.view.last_offset[1]) / self.view.last_scale
        found = False
        for tid, obj in getattr(self.engine, 'current_objects', {}).items():
            x1, y1, x2, y2 = obj['bbox']
            if x1 <= x_click <= x2 and y1 <= y_click <= y2:
                self.selected_track_id = tid
                self.view.show_crop(obj.get('crop'))
                class_name = obj.get('class_name', '')
                ocr_text = obj.get('ocr', '...')
                detail = f'\U0001f194 ID Tracking: {tid}\n'
                if class_name:
                    detail += f'\U0001f6f3 Lo\u1ea1i: {class_name}\n'
                if ocr_text and ocr_text != '...':
                    detail += f'\U0001f522 S\u1ed1 hi\u1ec7u: {ocr_text}\n'
                    detail += '\u2705 OCR ho\u00e0n t\u1ea5t'
                else:
                    detail += '\U0001f504 \u0110ang ph\u00e2n t\u00edch s\u1ed1 hi\u1ec7u...'
                    # Trigger manual OCR nếu chưa có kết quả
                    if self.engine.use_ocr and self.engine.ocr_engine is not None:
                        self.engine.request_manual_ocr(tid)
                self.view.show_detail_text(detail)
                found = True
                break
        if not found:
            self.view.show_detail_text('Không tìm thấy tàu tại vị trí click.\nClick vào bounding box để xem chi tiết.')

    def on_auto_ocr_complete(self, track_id, so_hieu, confidence=1.0, class_name='Unknown', crop_path=''):
        self.log_controller.on_auto_ocr_complete(track_id, so_hieu, confidence, class_name, crop_path)

    def _on_ocr_result_for_detail(self, track_id, text, score):
        """Callback từ OCR worker — cập nhật detail_text nếu tàu đang được chọn."""
        if track_id != self.selected_track_id:
            return
        obj = getattr(self.engine, 'current_objects', {}).get(track_id, {})
        class_name = obj.get('class_name', '')
        def _update():
            detail = f'\U0001f194 ID Tracking: {track_id}\n'
            if class_name:
                detail += f'\U0001f6f3 Lo\u1ea1i: {class_name}\n'
            detail += f'\U0001f522 S\u1ed1 hi\u1ec7u: {text}\n'
            detail += f'\u2705 \u0110\u1ed9 tin c\u1eady: {score:.1%}'
            self.view.show_detail_text(detail)
        self.root.after(0, _update)

    def _start_progress_polling(self):
        self._stop_progress_polling()
        self._update_progress()

    def _update_progress(self):
        if self.engine and (not self.engine.stop_event):
            current = getattr(self.engine, 'current_frame', 0)
            total = getattr(self.engine, 'total_frames', 0)
            self.view.update_progress(current, total)
            violating_ids = getattr(self.engine, 'violating_ids', set())
            if violating_ids:
                ids_str = ', '.join(map(str, sorted(violating_ids)))
                self.view.alert_label.config(text=f'🚨 CẢNH BÁO: Tàu ID {ids_str} xâm nhập vùng cấm!')
            else:
                self.view.alert_label.config(text='')
            self._progress_poll_id = self.root.after(500, self._update_progress)
        else:
            if self.engine:
                current = getattr(self.engine, 'current_frame', 0)
                total = getattr(self.engine, 'total_frames', 0)
                self.view.update_progress(current, total)
            self.view.alert_label.config(text='')
            self._progress_poll_id = None

    def _stop_progress_polling(self):
        if self._progress_poll_id is not None:
            self.root.after_cancel(self._progress_poll_id)
            self._progress_poll_id = None

    def get_selected_alert_id(self):
        try:
            selection = self.view.alerts_view.alerts_tree.selection()
            if selection:
                item_id = selection[0]
                values = self.view.alerts_view.alerts_tree.item(item_id, 'values')
                if values:
                    return values[0]
        except:
            pass
        return None

    def on_closing(self):
        self.stop_process()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
