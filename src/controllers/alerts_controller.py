from datetime import datetime
from typing import List, Optional, Dict
from src.utils.sql_logger import SQLLogger, get_sql_logger
from src.controllers.auth_controller import CurrentUser, require_permission, Permission
from src.config.db_config import get_connection

class AlertsController:
    STATUS_NEW = 'new'
    STATUS_REVIEWED = 'reviewed'
    STATUS_RESOLVED = 'resolved'
    VALID_STATUSES = [STATUS_NEW, STATUS_REVIEWED, STATUS_RESOLVED]

    @staticmethod
    def get_alert(alert_id: int) -> Optional[Dict]:
        try:
            conn = get_connection()
            if not conn:
                return None
            cursor = conn.cursor()
            cursor.execute('\n                SELECT alert_id, unique_id, track_id, session_id, alert_type, alert_time,\n                       center_x, center_y, loai_tau, so_hieu, do_tin_cay_ocr, \n                       telegram_sent, hinh_anh, ghi_chu, status, handled_by, handled_at, note\n                FROM alerts WHERE alert_id = ?\n            ', (alert_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return {'alert_id': row[0], 'unique_id': row[1], 'track_id': row[2], 'session_id': row[3], 'alert_type': row[4], 'alert_time': row[5], 'center_x': row[6], 'center_y': row[7], 'loai_tau': row[8], 'so_hieu': row[9], 'do_tin_cay_ocr': row[10], 'telegram_sent': bool(row[11]), 'hinh_anh': row[12], 'ghi_chu': row[13], 'status': row[14], 'handled_by': row[15], 'handled_at': row[16], 'note': row[17]}
        except Exception as e:
            print(f'>> Error getting alert: {e}')
            return None

    @staticmethod
    def get_alerts(status: Optional[str]=None, limit: int=100) -> List[Dict]:
        try:
            conn = get_connection()
            if not conn:
                return []
            cursor = conn.cursor()
            if status:
                query = '\n                    SELECT alert_id, unique_id, track_id, session_id, alert_type, alert_time,\n                           center_x, center_y, loai_tau, so_hieu, do_tin_cay_ocr, \n                           telegram_sent, hinh_anh, ghi_chu, status, handled_by, handled_at, note\n                    FROM alerts WHERE status = ? ORDER BY alert_time DESC\n                '
                cursor.execute(query, (status,))
            else:
                query = '\n                    SELECT alert_id, unique_id, track_id, session_id, alert_type, alert_time,\n                           center_x, center_y, loai_tau, so_hieu, do_tin_cay_ocr, \n                           telegram_sent, hinh_anh, ghi_chu, status, handled_by, handled_at, note\n                    FROM alerts ORDER BY alert_time DESC\n                '
                cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            alerts = []
            for row in rows[:limit]:
                alerts.append({'alert_id': row[0], 'unique_id': row[1], 'track_id': row[2], 'session_id': row[3], 'alert_type': row[4], 'alert_time': row[5], 'center_x': row[6], 'center_y': row[7], 'loai_tau': row[8], 'so_hieu': row[9], 'do_tin_cay_ocr': row[10], 'telegram_sent': bool(row[11]), 'hinh_anh': row[12], 'ghi_chu': row[13], 'status': row[14], 'handled_by': row[15], 'handled_at': row[16], 'note': row[17]})
            return alerts
        except Exception as e:
            print(f'>> Error getting alerts: {e}')
            return []

    @staticmethod
    @require_permission(Permission.MANAGE_ALERTS)
    def update_alert_status(alert_id: int, new_status: str, note: str='') -> bool:
        if new_status not in AlertsController.VALID_STATUSES:
            print(f'>> Invalid status: {new_status}')
            return False
        try:
            current_user = CurrentUser()
            if not current_user.is_authenticated():
                print('>> User not authenticated')
                return False
            conn = get_connection()
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute('\n                UPDATE alerts \n                SET status = ?, handled_by = ?, handled_at = ?, note = ?\n                WHERE alert_id = ?\n            ', (new_status, current_user.user_id, datetime.now(), note, alert_id))
            conn.commit()
            conn.close()
            status_name = {AlertsController.STATUS_NEW: 'Mới', AlertsController.STATUS_REVIEWED: 'Đã xem xét', AlertsController.STATUS_RESOLVED: 'Đã xử lý xong'}.get(new_status, new_status)
            print(f'✅ Cập nhật cảnh báo #{alert_id} → {status_name} (xử lý bởi: {current_user.full_name})')
            return True
        except Exception as e:
            print(f'>> Error updating alert status: {e}')
            return False

    @staticmethod
    @require_permission(Permission.MANAGE_ALERTS)
    def add_note_to_alert(alert_id: int, note: str) -> bool:
        try:
            current_user = CurrentUser()
            if not current_user.is_authenticated():
                return False
            conn = get_connection()
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute('SELECT note FROM alerts WHERE alert_id = ?', (alert_id,))
            row = cursor.fetchone()
            old_note = row[0] if row and row[0] else ''
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            new_note = f'{old_note}\n[{timestamp} - {current_user.full_name}]: {note}' if old_note else f'[{timestamp} - {current_user.full_name}]: {note}'
            cursor.execute('\n                UPDATE alerts \n                SET note = ?, handled_by = ?, handled_at = ?\n                WHERE alert_id = ?\n            ', (new_note, current_user.user_id, datetime.now(), alert_id))
            conn.commit()
            conn.close()
            print(f'✅ Đã thêm ghi chú cho cảnh báo #{alert_id}')
            return True
        except Exception as e:
            print(f'>> Error adding note: {e}')
            return False

    @staticmethod
    def get_statistics() -> Dict:
        try:
            conn = get_connection()
            if not conn:
                return {}
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM alerts')
            total = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM alerts WHERE status = ?', (AlertsController.STATUS_NEW,))
            new_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM alerts WHERE status = ?', (AlertsController.STATUS_REVIEWED,))
            reviewed_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM alerts WHERE status = ?', (AlertsController.STATUS_RESOLVED,))
            resolved_count = cursor.fetchone()[0]
            conn.close()
            return {'total': total, 'new': new_count, 'reviewed': reviewed_count, 'resolved': resolved_count}
        except Exception as e:
            print(f'>> Error getting statistics: {e}')
            return {}

    @staticmethod
    def update_sql_logger_alert(sql_logger: SQLLogger, alert_id: int, status: str, note: str='') -> bool:
        try:
            current_user = CurrentUser()
            conn = sql_logger.get_connection()
            if not conn:
                conn = get_connection()
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute('\n                UPDATE alerts \n                SET status = ?, handled_by = ?, handled_at = ?, note = ?\n                WHERE alert_id = ?\n            ', (status, current_user.user_id if current_user.is_authenticated() else None, datetime.now(), note, alert_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'>> Error updating alert via SQL logger: {e}')
            return False
