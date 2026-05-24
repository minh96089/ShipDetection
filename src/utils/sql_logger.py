import os
from datetime import datetime
from threading import Lock
from typing import List, Dict, Optional
import pyodbc
from src.config.db_config import get_connection

class SQLLogger:

    def __init__(self, log_dir: str=None):
        self.lock = Lock()
        if log_dir is None:
            log_dir = 'outputs'
        self.log_dir = log_dir

    def _ensure_ship_exists(self, cursor, so_hieu: str, loai_tau: str, hinh_anh: str=''):
        if not so_hieu or so_hieu == 'N/A' or so_hieu == 'None':
            return
        cursor.execute('SELECT so_hieu, anh_dai_dien FROM ship WHERE so_hieu = ?', (so_hieu,))
        row = cursor.fetchone()
        if not row:
            try:
                cursor.execute('\n                    INSERT INTO ship (so_hieu, loai_tau, anh_dai_dien)\n                    VALUES (?, ?, ?)\n                ', (so_hieu, loai_tau, hinh_anh))
            except pyodbc.Error as e:
                print(f'>> SQL Warning: Không thể insert vào bảng ship ({so_hieu}): {e}')
        elif not row.anh_dai_dien and hinh_anh:
            try:
                cursor.execute('UPDATE ship SET anh_dai_dien = ? WHERE so_hieu = ?', (hinh_anh, so_hieu))
            except pyodbc.Error:
                pass

    def append_log(self, track_id: int, session_id: str, class_name: str, video_source: str, so_hieu_ocr: str='N/A', do_tin_cay_ocr: float=0.0, hinh_anh_path: str='', gio_phat_hien: str=None) -> int:
        if gio_phat_hien is None:
            gio_phat_hien = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        unique_id = f'{session_id}_{track_id}'
        actual_so_hieu = None if so_hieu_ocr == 'N/A' or so_hieu_ocr == '' else str(so_hieu_ocr)
        with self.lock:
            conn = get_connection()
            if not conn:
                return -1
            try:
                cursor = conn.cursor()
                if actual_so_hieu:
                    self._ensure_ship_exists(cursor, actual_so_hieu, class_name, hinh_anh_path)
                cursor.execute('SELECT unique_id FROM shiplog WHERE unique_id = ?', (unique_id,))
                if cursor.fetchone():
                    cursor.execute("\n                        UPDATE shiplog \n                        SET hinh_anh = CASE WHEN ? != '' THEN ? ELSE hinh_anh END,\n                            so_hieu = ?,\n                            do_tin_cay_ocr = ?\n                        WHERE unique_id = ?\n                    ", (hinh_anh_path, hinh_anh_path, actual_so_hieu, do_tin_cay_ocr, unique_id))
                    print(f'>> SQL: Cập nhật entry [unique_id={unique_id}, class={class_name}]')
                else:
                    cursor.execute('\n                        INSERT INTO shiplog (unique_id, track_id, loai_tau, gio_phat_hien, hinh_anh, nguon, so_hieu, do_tin_cay_ocr)\n                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n                    ', (unique_id, track_id, class_name, gio_phat_hien, hinh_anh_path, video_source, actual_so_hieu, do_tin_cay_ocr))
                    print(f'>> SQL: Thêm log [unique_id={unique_id}, class={class_name}]')
                conn.commit()
                return 1
            except pyodbc.Error as e:
                print(f'>> SQL Error trong append_log: {e}')
                return -1
            finally:
                conn.close()

    def update_log(self, track_id: int, session_id: str, so_hieu_ocr: str=None, do_tin_cay_ocr: float=None, hinh_anh_path: str=None) -> bool:
        unique_id = f'{session_id}_{track_id}'
        return self.update_log_by_unique_id(unique_id, so_hieu_ocr, do_tin_cay_ocr, hinh_anh_path)

    def update_log_by_unique_id(self, unique_id: str, so_hieu_ocr: str=None, do_tin_cay_ocr: float=None, hinh_anh_path: str=None) -> bool:
        with self.lock:
            conn = get_connection()
            if not conn:
                return False
            try:
                cursor = conn.cursor()
                cursor.execute('SELECT loai_tau FROM shiplog WHERE unique_id = ?', (unique_id,))
                row = cursor.fetchone()
                if not row:
                    print(f'>> SQL: Không tìm thấy unique_id={unique_id}')
                    return False
                loai_tau = row[0]
                updates = []
                params = []
                if so_hieu_ocr is not None:
                    actual_so_hieu = None if so_hieu_ocr == 'N/A' or so_hieu_ocr == '' else str(so_hieu_ocr)
                    if actual_so_hieu:
                        self._ensure_ship_exists(cursor, actual_so_hieu, loai_tau, hinh_anh_path if hinh_anh_path else '')
                    updates.append('so_hieu = ?')
                    params.append(actual_so_hieu)
                if do_tin_cay_ocr is not None:
                    updates.append('do_tin_cay_ocr = ?')
                    params.append(do_tin_cay_ocr)
                if hinh_anh_path is not None:
                    updates.append('hinh_anh = ?')
                    params.append(hinh_anh_path)
                if not updates:
                    return True
                params.append(unique_id)
                query = f"UPDATE shiplog SET {', '.join(updates)} WHERE unique_id = ?"
                cursor.execute(query, tuple(params))
                conn.commit()
                print(f'>> SQL: Cập nhật unique_id={unique_id} thành công')
                return True
            except pyodbc.Error as e:
                print(f'>> SQL Error trong update_log_by_unique_id: {e}')
                return False
            finally:
                conn.close()

    def get_all_logs(self) -> List[Dict]:
        conn = get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute('\n                SELECT unique_id, track_id, loai_tau AS class_name, gio_phat_hien, hinh_anh AS hinh_anh_path, nguon AS video_source, so_hieu AS so_hieu_ocr, do_tin_cay_ocr, ghi_chu\n                FROM shiplog\n                ORDER BY gio_phat_hien DESC\n            ')
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                row_dict['so_hieu_ocr'] = row_dict['so_hieu_ocr'] if row_dict['so_hieu_ocr'] is not None else 'N/A'
                parts = row_dict['unique_id'].rsplit('_', 1)
                row_dict['session_id'] = parts[0] if len(parts) > 1 else row_dict['unique_id']
                results.append(row_dict)
            return results
        except pyodbc.Error as e:
            print(f'>> SQL Error: {e}')
            return []
        finally:
            conn.close()

    def get_logs_by_session(self, session_id: str) -> List[Dict]:
        conn = get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            search_pattern = f'{session_id}_%'
            cursor.execute('\n                SELECT unique_id, track_id, loai_tau AS class_name, gio_phat_hien, hinh_anh AS hinh_anh_path, nguon AS video_source, so_hieu AS so_hieu_ocr, do_tin_cay_ocr\n                FROM shiplog\n                WHERE unique_id LIKE ?\n                ORDER BY gio_phat_hien DESC\n            ', (search_pattern,))
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                row_dict['so_hieu_ocr'] = row_dict['so_hieu_ocr'] if row_dict['so_hieu_ocr'] is not None else 'N/A'
                row_dict['session_id'] = session_id
                results.append(row_dict)
            return results
        except pyodbc.Error as e:
            print(f'>> SQL Error: {e}')
            return []
        finally:
            conn.close()

    def get_logs_by_so_hieu(self, so_hieu: str) -> List[Dict]:
        conn = get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute('\n                SELECT unique_id, track_id, loai_tau AS class_name, gio_phat_hien, hinh_anh AS hinh_anh_path, nguon AS video_source, so_hieu AS so_hieu_ocr, do_tin_cay_ocr\n                FROM shiplog\n                WHERE so_hieu = ?\n                ORDER BY gio_phat_hien DESC\n            ', (so_hieu,))
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                parts = row_dict['unique_id'].rsplit('_', 1)
                row_dict['session_id'] = parts[0] if len(parts) > 1 else row_dict['unique_id']
                results.append(row_dict)
            return results
        except pyodbc.Error as e:
            print(f'>> SQL Error: {e}')
            return []
        finally:
            conn.close()

    def get_log_by_track_id(self, track_id: int, session_id: str) -> Optional[Dict]:
        unique_id = f'{session_id}_{track_id}'
        conn = get_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor()
            cursor.execute('\n                SELECT unique_id, track_id, loai_tau AS class_name, gio_phat_hien, hinh_anh AS hinh_anh_path, nguon AS video_source, so_hieu AS so_hieu_ocr, do_tin_cay_ocr\n                FROM shiplog\n                WHERE unique_id = ?\n            ', (unique_id,))
            row = cursor.fetchone()
            if not row:
                return None
            columns = [column[0] for column in cursor.description]
            row_dict = dict(zip(columns, row))
            row_dict['so_hieu_ocr'] = row_dict['so_hieu_ocr'] if row_dict['so_hieu_ocr'] is not None else 'N/A'
            row_dict['session_id'] = session_id
            return row_dict
        except pyodbc.Error as e:
            print(f'>> SQL Error: {e}')
            return None
        finally:
            conn.close()

    def update_ghi_chu(self, unique_id: str, ghi_chu: str) -> bool:
        with self.lock:
            conn = get_connection()
            if not conn:
                return False
            try:
                cursor = conn.cursor()
                cursor.execute('UPDATE shiplog SET ghi_chu = ? WHERE unique_id = ?', (ghi_chu if ghi_chu else None, unique_id))
                conn.commit()
                print(f'>> SQL: Cập nhật ghi_chu cho unique_id={unique_id}')
                return True
            except pyodbc.Error as e:
                print(f'>> SQL Error trong update_ghi_chu: {e}')
                return False
            finally:
                conn.close()

    def log_trajectory(self, unique_id: str, session_id: str, track_id: int, frame_index: int, center_x: int, center_y: int, bbox_x1: int=None, bbox_y1: int=None, bbox_x2: int=None, bbox_y2: int=None, confidence: float=None) -> bool:
        with self.lock:
            conn = get_connection()
            if not conn:
                return False
            try:
                cursor = conn.cursor()
                cursor.execute('\n                    INSERT INTO ship_trajectory\n                        (unique_id, session_id, track_id, frame_index,\n                         center_x, center_y, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence)\n                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n                ', (unique_id, session_id, track_id, frame_index, center_x, center_y, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence))
                conn.commit()
                return True
            except pyodbc.Error as e:
                print(f'>> SQL Error (trajectory): {e}')
                return False
            finally:
                conn.close()

    def get_trajectory(self, session_id: str, track_id: int) -> List[Dict]:
        conn = get_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute('\n                SELECT frame_index, center_x, center_y,\n                       bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, thoi_gian\n                FROM ship_trajectory\n                WHERE session_id = ? AND track_id = ?\n                ORDER BY frame_index ASC\n            ', (session_id, track_id))
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except pyodbc.Error as e:
            print(f'>> SQL Error (get_trajectory): {e}')
            return []
        finally:
            conn.close()

    def get_all_trajectories_in_session(self, session_id: str) -> Dict[int, List[Dict]]:
        conn = get_connection()
        if not conn:
            return {}
        try:
            cursor = conn.cursor()
            cursor.execute('\n                SELECT track_id, frame_index, center_x, center_y,\n                       bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, thoi_gian\n                FROM ship_trajectory\n                WHERE session_id = ?\n                ORDER BY track_id, frame_index ASC\n            ', (session_id,))
            columns = [col[0] for col in cursor.description]
            result: Dict[int, List[Dict]] = {}
            for row in cursor.fetchall():
                d = dict(zip(columns, row))
                tid = d['track_id']
                result.setdefault(tid, []).append(d)
            return result
        except pyodbc.Error as e:
            print(f'>> SQL Error (get_all_trajectories): {e}')
            return {}
        finally:
            conn.close()

    def log_violation_alert(self, unique_id: str, track_id: int, session_id: str, center_x: int, center_y: int, loai_tau: str='', so_hieu: str='', do_tin_cay_ocr: float=0.0, telegram_sent: bool=False, hinh_anh: str='', ghi_chu: str='') -> bool:
        with self.lock:
            conn = get_connection()
            if not conn:
                return False
            try:
                cursor = conn.cursor()
                track_id = int(track_id)
                center_x = int(center_x)
                center_y = int(center_y)
                do_tin_cay_ocr = float(do_tin_cay_ocr)
                actual_so_hieu = None if so_hieu == 'N/A' or so_hieu == '' else str(so_hieu)
                cursor.execute('\n                    INSERT INTO alerts (unique_id, track_id, session_id, alert_type, center_x, center_y, \n                                      loai_tau, so_hieu, do_tin_cay_ocr, telegram_sent, hinh_anh, ghi_chu,\n                                      status, handled_by, handled_at, note)\n                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n                ', (unique_id, track_id, session_id, 'Xâm nhập vùng cấm', center_x, center_y, loai_tau, actual_so_hieu, do_tin_cay_ocr, 1 if telegram_sent else 0, hinh_anh, ghi_chu, 'new', None, None, ''))
                conn.commit()
                print(f'>> SQL: Ghi cảnh báo vi phạm [track_id={track_id}, unique_id={unique_id}]')
                return True
            except pyodbc.Error as e:
                print(f'>> SQL Error (log_violation_alert): {e}')
                return False
            finally:
                conn.close()
_sql_logger_instance: Optional[SQLLogger] = None

def get_sql_logger(log_dir: str=None) -> SQLLogger:
    global _sql_logger_instance
    if _sql_logger_instance is None:
        _sql_logger_instance = SQLLogger(log_dir)
    return _sql_logger_instance

def reset_sql_logger():
    global _sql_logger_instance
    _sql_logger_instance = None
