import tkinter as tk
from tkinter import messagebox
from src.controllers.alerts_controller import AlertsController
from src.controllers.auth_controller import AuthController, Permission
from datetime import datetime

class AlertsViewController:

    def __init__(self, alerts_view, root):
        self.view = alerts_view
        self.root = root
        self.output_folder = None
        self.view.on_refresh_alerts = self.load_alerts
        self.view.refresh_alerts(callback=self.load_alerts)

    def set_output_folder(self, folder):
        self.output_folder = folder

    def load_alerts(self):
        try:
            if not AuthController.has_permission(Permission.VIEW_ALERTS):
                messagebox.showwarning('Quyền hạn chế', 'Bạn không có quyền xem cảnh báo')
                return
            alerts = AlertsController.get_alerts()
            self.view.set_alerts_data(alerts)
            stats = AlertsController.get_statistics()
            stats_text = f"Tổng: {stats.get('total', 0)} | Mới: {stats.get('new', 0)} | Đã xem: {stats.get('reviewed', 0)} | Đã xử lý xong: {stats.get('resolved', 0)}"
            self.view.stats_label.config(text=stats_text)
            print(f'✅ Đã load {len(alerts)} cảnh báo')
        except Exception as e:
            print(f'❌ Lỗi load alerts: {e}')

    def on_mark_reviewed(self, status, alert_id):
        try:
            AlertsController.update_alert_status(alert_id=int(alert_id), new_status='reviewed', note='Đã xem')
            messagebox.showinfo('Thành công', f"Cảnh báo #{alert_id} đã được đánh dấu là 'Đã xem'")
            self.load_alerts()
        except PermissionError as e:
            messagebox.showerror('Quyền hạn chế', str(e))
        except Exception as e:
            messagebox.showerror('Lỗi', f'Không thể cập nhật: {e}')

    def on_mark_resolved(self, status, alert_id):
        try:
            AlertsController.update_alert_status(alert_id=int(alert_id), new_status='resolved', note='Đã xử lý xong')
            messagebox.showinfo('Thành công', f"Cảnh báo #{alert_id} đã được đánh dấu là 'Đã xử lý xong'")
            self.load_alerts()
        except PermissionError as e:
            messagebox.showerror('Quyền hạn chế', str(e))
        except Exception as e:
            messagebox.showerror('Lỗi', f'Không thể cập nhật: {e}')

    def on_add_note(self, note_content, alert_id):
        try:
            AlertsController.add_note_to_alert(alert_id=int(alert_id), note=note_content)
            messagebox.showinfo('Thành công', f'Ghi chú đã được thêm cho cảnh báo #{alert_id}')
            self.load_alerts()
        except PermissionError as e:
            messagebox.showerror('Quyền hạn chế', str(e))
        except Exception as e:
            messagebox.showerror('Lỗi', f'Không thể thêm ghi chú: {e}')
