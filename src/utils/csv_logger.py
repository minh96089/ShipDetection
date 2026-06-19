import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime
from threading import Lock
from pathlib import Path
from typing import List, Dict, Optional

class CSVLogger:
    CSV_COLUMNS = ['log_id', 'unique_id', 'track_id', 'session_id', 'class_name', 'so_hieu_ocr', 'do_tin_cay_ocr', 'gio_phat_hien', 'hinh_anh_path', 'video_source']
    CSV_DTYPES = {'log_id': 'int64', 'unique_id': 'str', 'track_id': 'int64', 'session_id': 'str', 'class_name': 'str', 'so_hieu_ocr': 'object', 'do_tin_cay_ocr': 'float64', 'gio_phat_hien': 'str', 'hinh_anh_path': 'str', 'video_source': 'str'}

    def __init__(self, log_dir: str=None):
        if log_dir is None:
            log_dir = 'outputs'
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.log_dir / 'shiplog.csv'
        self.lock = Lock()
        self._initialize_csv()
        self.log_counter = self._get_next_log_id()

    def _read_csv_with_dtypes(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.csv_path, dtype=self.CSV_DTYPES, na_values=['nan', 'NaN', ''])
            return df
        except Exception as e:
            print(f'>> CSV Warning: Lỗi đọc CSV với dtype cụ thể, thử đọc bình thường: {e}')
            try:
                return pd.read_csv(self.csv_path)
            except Exception as e2:
                print(f'>> CSV Error: Lỗi đọc CSV: {e2}')
                return pd.DataFrame()

    def _ensure_correct_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'so_hieu_ocr' in df.columns:
            df['so_hieu_ocr'] = df['so_hieu_ocr'].astype('object')
            df['so_hieu_ocr'] = df['so_hieu_ocr'].fillna('N/A')
        return df

    def _initialize_csv(self):
        if not self.csv_path.exists() or self.csv_path.stat().st_size == 0:
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_COLUMNS)
            print(f'>> CSV Logger: Tạo mới file {self.csv_path} (File trống hoặc chưa có)')
        else:
            try:
                df = self._read_csv_with_dtypes()
                modified = False
                if 'unique_id' not in df.columns:
                    print('>> CSV Logger: Phát hiện file cũ - migrating để thêm cột unique_id...')
                    df['unique_id'] = df['session_id'] + '_' + df['track_id'].astype(str)
                    modified = True
                if 'toc_do_tb' in df.columns:
                    print('>> CSV Logger: Phát hiện file cũ - xóa bỏ cột toc_do_tb thừa...')
                    df = df.drop(columns=['toc_do_tb'])
                    modified = True
                if modified or list(df.columns) != self.CSV_COLUMNS:
                    print('>> CSV Logger: Cập nhật lại cấu trúc CSV...')
                    for col in self.CSV_COLUMNS:
                        if col not in df.columns:
                            df[col] = None
                    df = df[self.CSV_COLUMNS]
                    df = self._ensure_correct_dtypes(df)
                    df.to_csv(self.csv_path, index=False, encoding='utf-8')
                    print('>> CSV Logger: Migration thành công')
                else:
                    print(f'>> CSV Logger: Sử dụng file {self.csv_path}')
            except Exception as e:
                print(f'>> CSV Logger Warning: {e}, sẽ tiếp tục...')

    def _get_next_log_id(self) -> int:
        try:
            df = self._read_csv_with_dtypes()
            if df.empty:
                return 1
            return int(df['log_id'].max()) + 1 if 'log_id' in df.columns else 1
        except Exception as e:
            print(f'>> Warning: Lỗi đọc log_id từ CSV: {e}')
            return 1

    def append_log(self, track_id: int, session_id: str, class_name: str, video_source: str, so_hieu_ocr: str='N/A', do_tin_cay_ocr: float=0.0, hinh_anh_path: str='', gio_phat_hien: str=None) -> int:
        if gio_phat_hien is None:
            gio_phat_hien = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        unique_id = f'{session_id}_{track_id}'
        with self.lock:
            try:
                df = self._read_csv_with_dtypes()
                df = self._ensure_correct_dtypes(df)
                existing_mask = (df['session_id'] == session_id) & (df['track_id'] == track_id)
                if not existing_mask.empty and existing_mask.any():
                    existing_rows = df[existing_mask]
                    last_idx = existing_rows.index[-1]
                    if hinh_anh_path:
                        df.at[last_idx, 'hinh_anh_path'] = hinh_anh_path
                    df = self._ensure_correct_dtypes(df)
                    df.to_csv(self.csv_path, index=False, encoding='utf-8')
                    log_id = int(df.at[last_idx, 'log_id'])
                    print(f'>> CSV: Cập nhật entry [unique_id={unique_id}, class={class_name}]')
                    return log_id
                log_id = self.log_counter
                self.log_counter += 1
                row = [log_id, unique_id, track_id, session_id, class_name, so_hieu_ocr, do_tin_cay_ocr, gio_phat_hien, hinh_anh_path, video_source]
                with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
                print(f'>> CSV: Thêm log [unique_id={unique_id}, class={class_name}]')
                return log_id
            except Exception as e:
                print(f'>> CSV Error: Lỗi append_log: {e}')
                return -1

    def update_log(self, track_id: int, session_id: str, so_hieu_ocr: str=None, do_tin_cay_ocr: float=None, hinh_anh_path: str=None) -> bool:
        with self.lock:
            try:
                df = self._read_csv_with_dtypes()
                mask = (df['track_id'] == track_id) & (df['session_id'] == session_id)
                matching_rows = df[mask]
                if matching_rows.empty:
                    print(f'>> CSV: Không tìm thấy track_id={track_id} trong session={session_id}')
                    return False
                last_idx = matching_rows.index[-1]
                if so_hieu_ocr is not None:
                    df.at[last_idx, 'so_hieu_ocr'] = str(so_hieu_ocr) if so_hieu_ocr != 'N/A' else so_hieu_ocr
                if do_tin_cay_ocr is not None:
                    df.at[last_idx, 'do_tin_cay_ocr'] = float(do_tin_cay_ocr)
                if hinh_anh_path is not None:
                    df.at[last_idx, 'hinh_anh_path'] = hinh_anh_path
                df = self._ensure_correct_dtypes(df)
                df.to_csv(self.csv_path, index=False, encoding='utf-8')
                update_str = []
                if so_hieu_ocr is not None:
                    update_str.append(f'so_hieu={so_hieu_ocr}')
                if do_tin_cay_ocr is not None:
                    update_str.append(f'confidence={do_tin_cay_ocr:.1%}')
                print(f">> CSV: Cập nhật track_id={track_id}: {' | '.join(update_str)}")
                return True
            except Exception as e:
                print(f'>> CSV Error: Lỗi update_log: {e}')
                import traceback
                traceback.print_exc()
                return False

    def update_log_by_unique_id(self, unique_id: str, so_hieu_ocr: str=None, do_tin_cay_ocr: float=None, hinh_anh_path: str=None) -> bool:
        with self.lock:
            try:
                df = self._read_csv_with_dtypes()
                mask = df['unique_id'] == unique_id
                matching_rows = df[mask]
                if matching_rows.empty:
                    print(f'>> CSV: Không tìm thấy unique_id={unique_id}')
                    return False
                last_idx = matching_rows.index[-1]
                if so_hieu_ocr is not None:
                    df.at[last_idx, 'so_hieu_ocr'] = str(so_hieu_ocr) if so_hieu_ocr != 'N/A' else so_hieu_ocr
                if do_tin_cay_ocr is not None:
                    df.at[last_idx, 'do_tin_cay_ocr'] = float(do_tin_cay_ocr)
                if hinh_anh_path is not None:
                    df.at[last_idx, 'hinh_anh_path'] = hinh_anh_path
                df = self._ensure_correct_dtypes(df)
                df.to_csv(self.csv_path, index=False, encoding='utf-8')
                update_str = []
                if so_hieu_ocr is not None:
                    update_str.append(f'so_hieu={so_hieu_ocr}')
                if do_tin_cay_ocr is not None:
                    update_str.append(f'confidence={do_tin_cay_ocr:.1%}')
                print(f">> CSV: Cập nhật unique_id={unique_id}: {' | '.join(update_str)}")
                return True
            except Exception as e:
                print(f'>> CSV Error: Lỗi update_log_by_unique_id: {e}')
                import traceback
                traceback.print_exc()
                return False

    def get_all_logs(self) -> List[Dict]:
        try:
            df = self._read_csv_with_dtypes()
            df = self._ensure_correct_dtypes(df)
            if df.empty:
                return []
            df_sorted = df.sort_values('gio_phat_hien', ascending=False)
            return df_sorted.to_dict('records')
        except Exception as e:
            print(f'>> CSV Error: Lỗi get_all_logs: {e}')
            return []

    def get_logs_by_session(self, session_id: str) -> List[Dict]:
        try:
            df = self._read_csv_with_dtypes()
            df = self._ensure_correct_dtypes(df)
            df_session = df[df['session_id'] == session_id]
            if df_session.empty:
                return []
            return df_session.sort_values('gio_phat_hien', ascending=False).to_dict('records')
        except Exception as e:
            print(f'>> CSV Error: Lỗi get_logs_by_session: {e}')
            return []

    def get_logs_by_so_hieu(self, so_hieu: str) -> List[Dict]:
        try:
            df = self._read_csv_with_dtypes()
            df = self._ensure_correct_dtypes(df)
            df_ship = df[df['so_hieu_ocr'] == so_hieu]
            if df_ship.empty:
                return []
            return df_ship.sort_values('gio_phat_hien', ascending=False).to_dict('records')
        except Exception as e:
            print(f'>> CSV Error: Lỗi get_logs_by_so_hieu: {e}')
            return []

    def get_log_by_track_id(self, track_id: int, session_id: str) -> Optional[Dict]:
        try:
            df = self._read_csv_with_dtypes()
            df = self._ensure_correct_dtypes(df)
            mask = (df['track_id'] == track_id) & (df['session_id'] == session_id)
            matching = df[mask]
            if matching.empty:
                return None
            return matching.iloc[-1].to_dict()
        except Exception as e:
            print(f'>> CSV Error: Lỗi get_log_by_track_id: {e}')
            return None

    def delete_old_logs(self, days: int=30) -> int:
        with self.lock:
            try:
                df = self._read_csv_with_dtypes()
                df['gio_phat_hien'] = pd.to_datetime(df['gio_phat_hien'])
                cutoff_date = datetime.now() - pd.Timedelta(days=days)
                df_filtered = df[df['gio_phat_hien'] >= cutoff_date]
                deleted_count = len(df) - len(df_filtered)
                df_filtered = self._ensure_correct_dtypes(df_filtered)
                df_filtered.to_csv(self.csv_path, index=False, encoding='utf-8')
                print(f'>> CSV: Xóa {deleted_count} logs cũ hơn {days} ngày')
                return deleted_count
            except Exception as e:
                print(f'>> CSV Error: Lỗi delete_old_logs: {e}')
                return 0

    def get_csv_path(self) -> str:
        return str(self.csv_path)

    def get_log_dir(self) -> str:
        return str(self.log_dir)
_csv_logger_instance: Optional[CSVLogger] = None

def get_csv_logger(log_dir: str=None) -> CSVLogger:
    global _csv_logger_instance
    if _csv_logger_instance is None:
        _csv_logger_instance = CSVLogger(log_dir)
    return _csv_logger_instance

def reset_csv_logger():
    global _csv_logger_instance
    _csv_logger_instance = None
