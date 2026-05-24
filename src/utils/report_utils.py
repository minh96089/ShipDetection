import pandas as pd
import os
import numpy as np
import datetime

def save_test_report(data, all_confs, output_folder, video_name, processed_count, total_frames, model_name, imgsz, stride, conf_thresh, tag, ocr_data=None):
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_name = f'{timestamp}_{model_name}_{tag}_raw.csv'
    txt_name = f'{timestamp}_{model_name}_{tag}_REPORT.txt'
    ship_csv_name = f'{timestamp}_{model_name}_{tag}_SHIPS.csv'
    csv_path = os.path.join(output_folder, csv_name)
    txt_path = os.path.join(output_folder, txt_name)
    ship_csv_path = os.path.join(output_folder, ship_csv_name)
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)
    avg_fps = df['FPS'].mean()
    avg_time = df['Time_ms'].mean()
    total_detections = df['Objects_In_Frame'].sum() if 'Objects_In_Frame' in df.columns else df['Objects'].sum()
    overall_conf = np.mean(all_confs) if len(all_confs) > 0 else 0.0
    tracking_line = ''
    unique_count = 0
    if 'Total_Unique_Objects' in df.columns:
        unique_count = df['Total_Unique_Objects'].max()
        tracking_line = f'\n   - TRACKING (Số đối tượng thực tế): {unique_count}'
    ocr_section = ''
    if ocr_data and len(ocr_data) > 0:
        ocr_section = '\n4. DANH SÁCH MÃ HIỆU TÀU (OCR RESULT)\n'
        ocr_section += '   ID   | Mã Hiệu (Text)\n'
        ocr_section += '   -----|-------------------\n'
        ship_list = []
        for track_id, text in ocr_data.items():
            ocr_section += f'   {track_id:<5}| {text}\n'
            ship_list.append({'Track_ID': track_id, 'OCR_Text': text})
        if ship_list:
            pd.DataFrame(ship_list).to_csv(ship_csv_path, index=False)
            ocr_section += f'\n   (Đã lưu danh sách chi tiết tại: {ship_csv_name})'
    else:
        ocr_section = '\n4. KẾT QUẢ OCR\n   - Không có dữ liệu OCR hoặc không bật tính năng OCR.'
    report = f"\n==========================================================\nBÁO CÁO TEST TỰ ĐỘNG - {model_name}\n==========================================================\nThời gian: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nVideo Input: {video_name}\n----------------------------------------------------------\n1. CẤU HÌNH\n   - Model: {model_name}\n   - Size: {imgsz}\n   - Skip Frame: {stride}\n   - Confidence Thresh: {conf_thresh}\n\n2. KẾT QUẢ HIỆU NĂNG\n   - Tổng frames gốc: {total_frames}\n   - Số frame đã xử lý: {processed_count}\n   - FPS Trung bình: {avg_fps:.2f}\n   - Thời gian xử lý/frame: {avg_time:.2f} ms\n\n3. KẾT QUẢ NHẬN DIỆN\n   - Độ tin cậy trung bình (Confidence): {overall_conf:.4f}\n   - Tổng lượt phát hiện (All Detections): {total_detections}{tracking_line}\n\n{ocr_section}\n==========================================================\n    "
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(report)
    return (txt_path, report)
