import cv2
import time
import os
import threading
import queue
from ultralytics import YOLO
from src.utils.report_utils import save_test_report
from src.utils.sql_logger import get_sql_logger

class YoloTester:

    def __init__(self, model_path, input_source, output_folder, conf=0.5, imgsz=640, stride=1, use_ocr=False, text_model_path=None, tracker='bytetrack.yaml', use_tracking_trace=True, use_roi=False, roi_polygon=None):
        self.model_path = model_path
        self.input_source = input_source
        self.output_folder = output_folder
        self.conf = conf
        self.imgsz = imgsz
        self.stride = stride
        self.use_ocr = use_ocr
        self.tracker = tracker
        self.use_tracking_trace = use_tracking_trace
        self.track_history = {}
        self.use_roi = use_roi
        self.roi_polygon = roi_polygon if roi_polygon is not None else []
        self.violating_ids = set()
        self.stop_event = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.on_violation_alert = None
        self.ship_images_dir = os.path.join(self.output_folder, 'ship_images')
        os.makedirs(self.ship_images_dir, exist_ok=True)
        video_name = os.path.basename(input_source) if isinstance(input_source, str) else 'live_camera'
        self.session_id = f'{video_name}_{int(time.time())}'
        print(f'>> Session ID: {self.session_id}')
        print(f'>> Loading YOLO: {model_path}')
        self.model = YOLO(model_path)
        self.ocr_queue = queue.Queue()
        self.ocr_engine = None
        self.text_model = None
        if use_ocr:
            if text_model_path is None:
                raise ValueError('❌ text_model_path là bắt buộc khi use_ocr=True')
            if not os.path.exists(text_model_path):
                raise FileNotFoundError(f'❌ Không tìm thấy text model: {text_model_path}')
            try:
                print(f'>> Loading Text Detector: {text_model_path}')
                self.text_model = YOLO(text_model_path)
                print(f'>> Loading OCR Engine (PaddleOCR)')
                from src.engines.ocr_engine import ShipOCR
                self.ocr_engine = ShipOCR()
                threading.Thread(target=self.ocr_worker, daemon=True).start()
                print('>> OCR Worker thread started')
            except Exception as e:
                print(f'❌ Lỗi Init OCR: {e}')
                self.ocr_engine = None
                self.text_model = None
        self.ocr_cache = {}
        self.current_objects = {}
        self.all_confs = []
        self.current_frame = 0
        self.total_frames = 0
        self.class_short = {'fishing_boat': 'F', 'speed_boat': 'S', 'passenger': 'P', 'passenger_ship': 'P'}

    def ocr_worker(self):
        print('>> OCR Worker started (2-Stage: Text Detection → OCR)...')
        while True:
            try:
                item = self.ocr_queue.get(timeout=0.5)
                track_id, crop_img, is_priority, class_name, img_path = item
                if crop_img is None or crop_img.size == 0:
                    print(f'>> ⚠️ Skip track_id {track_id}: crop_img is empty')
                    self.ocr_queue.task_done()
                    continue
                text_crop = self._detect_text_region(crop_img, track_id)
                if text_crop is None:
                    print(f'>> ⚠️ Stage 1 Failed [track_id {track_id}]: Không detect được vùng chữ')
                    self.ocr_queue.task_done()
                    continue
                ocr_results = self._recognize_text(text_crop, track_id)
                if not ocr_results:
                    print(f'>> ⚠️ Stage 2 Failed [track_id {track_id}]: PaddleOCR không đọc được')
                    self.ocr_queue.task_done()
                    continue
                best = max(ocr_results, key=lambda x: x.get('score', 0))
                text = best['text'].strip().upper()
                score = best['score']
                if len(text) < 3:
                    print(f">> ⚠️ Skip [track_id {track_id}]: Text quá ngắn ('{text}')")
                    self.ocr_queue.task_done()
                    continue
                print(f'>> ✅ OCR Result [track_id {track_id}]: {text} ({score:.1%})')
                if track_id not in self.ocr_cache:
                    self.ocr_cache[track_id] = {'texts': [], 'final': None}
                self.ocr_cache[track_id]['final'] = text
                self._update_csv_after_ocr(track_id, text, score, class_name, img_path)
                self.ocr_queue.task_done()
            except queue.Empty:
                if self.stop_event:
                    break
            except Exception as e:
                print(f'❌ OCR Worker Error: {e}')
                try:
                    self.ocr_queue.task_done()
                except:
                    pass

    def _detect_text_region(self, ship_crop, track_id):
        try:
            if self.text_model is None:
                return None
            text_results = self.text_model(ship_crop, conf=0.5, verbose=False)
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
                x2 = min(ship_crop.shape[1], x2 + pad)
                y2 = min(ship_crop.shape[0], y2 + pad)
                if x2 - x1 < 10 or y2 - y1 < 10:
                    print(f'>> ⚠️ Text region quá nhỏ: {x2 - x1}x{y2 - y1}')
                    continue
                text_crop = ship_crop[y1:y2, x1:x2].copy()
                print(f'>> 🔍 Stage 1 OK [track_id {track_id}]: Detected text region {x2 - x1}x{y2 - y1}')
                break
            return text_crop
        except Exception as e:
            print(f'❌ Text Detection Error [track_id {track_id}]: {e}')
            return None

    def _recognize_text(self, text_crop, track_id):
        try:
            if self.ocr_engine is None:
                return None
            results = self.ocr_engine.ocr_image(text_crop)
            if not results:
                return None
            print(f'>> 🔤 Stage 2 OK [track_id {track_id}]: PaddleOCR found {len(results)} texts')
            return results
        except Exception as e:
            print(f'❌ Text Recognition Error [track_id {track_id}]: {e}')
            return None

    def _update_csv_after_ocr(self, track_id, text, score, class_name, img_path):
        try:
            sql_logger = get_sql_logger(self.output_folder)
            sql_logger.update_log(track_id=int(track_id), session_id=self.session_id, so_hieu_ocr=text, do_tin_cay_ocr=score, hinh_anh_path=img_path if img_path else None)
            print(f'>> ✅ Cập nhật SQL: so_hieu={text} | track_id={track_id} | confidence={score:.1%}')
        except Exception as e:
            print(f'❌ SQL Error (update after OCR): {e}')

    def request_manual_ocr(self, track_id):
        if not self.use_ocr or self.ocr_engine is None:
            print('>> ⚠️ OCR is not enabled or not initialized')
            return
        if track_id not in self.current_objects:
            print(f'>> ⚠️ Track ID {track_id} không tìm thấy')
            return
        obj = self.current_objects[track_id]
        crop_img = obj.get('crop')
        class_name = obj.get('class_name', 'Unknown')
        if crop_img is None or crop_img.size == 0:
            print(f'>> ⚠️ Ship crop is empty for track_id {track_id}')
            return
        print(f'>> 📌 Requesting manual OCR for track_id {track_id}...')
        self.ocr_queue.put((track_id, crop_img.copy(), True, class_name, None))

    def log_new_ship(self, track_id, class_name, crop_img=None, inside_roi=False):
        try:
            sql_logger = get_sql_logger(self.output_folder)
            existing = sql_logger.get_log_by_track_id(int(track_id), self.session_id)
            if existing is not None:
                return
            img_path = ''
            if crop_img is not None and crop_img.size > 0:
                img_filename = f'ship_{self.session_id}_{track_id}_{int(time.time())}.jpg'
                img_full_path = os.path.join(self.ship_images_dir, img_filename)
                cv2.imwrite(img_full_path, crop_img)
                img_path = img_full_path
                if self.use_ocr and self.ocr_engine is not None:
                    self.ocr_queue.put((track_id, crop_img.copy(), False, class_name, img_path))
                    print(f'>> 🔄 Auto-queued to OCR for track_id {track_id} ({class_name}) | Ảnh: {img_path}')
            video_name = os.path.basename(self.input_source) if isinstance(self.input_source, str) else 'live'
            sql_logger.append_log(track_id=int(track_id), session_id=self.session_id, class_name=class_name, video_source=video_name, so_hieu_ocr='N/A', do_tin_cay_ocr=0.0, hinh_anh_path=img_path)
            if inside_roi:
                sql_logger.update_ghi_chu(f'{self.session_id}_{track_id}', '[CẢNH BÁO XÂM NHẬP]')
            print(f'>> SQL: Logged New Detection track_id={track_id}')
        except Exception as e:
            print(f'>> SQL Insert Error: {e}')

    def run(self, update_gui_callback, on_done_callback=None):
        cap = cv2.VideoCapture(self.input_source)
        if not cap.isOpened():
            print('>> Không mở được video / camera!')
            return
        w_vid = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h_vid = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps_vid = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if fps_vid <= 0 or fps_vid > 120:
            print(f'>> ⚠️ FPS không hợp lệ ({fps_vid}), đặt lại về 30.0')
            fps_vid = 30.0
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.current_frame = 0
        import re
        if '://' in str(self.input_source):
            raw_name = f'live_stream_{int(time.time())}'
        else:
            base = os.path.splitext(os.path.basename(self.input_source))[0]
            base = re.sub('[^\\w\\-]', '_', base)
            raw_name = f'result_{base}_{int(time.time())}'
        video_filename = raw_name + '.mp4'
        save_path = os.path.join(self.output_folder, video_filename)
        out = None
        for fourcc_str, ext in [('avc1', '.mp4'), ('mp4v', '.mp4'), ('XVID', '.avi')]:
            _path = os.path.splitext(save_path)[0] + ext
            _out = cv2.VideoWriter(_path, cv2.VideoWriter_fourcc(*fourcc_str), fps_vid, (w_vid, h_vid))
            if _out.isOpened():
                out = _out
                save_path = _path
                print(f'>> VideoWriter OK: codec={fourcc_str} | path={_path}')
                break
            _out.release()
            print(f'>> VideoWriter failed with codec={fourcc_str}, thử codec khác...')
        if out is None:
            print('>> ⚠️ Không khởi tạo được VideoWriter — video sẽ không được lưu!')
        frame_count = 0
        frame_index = 0
        data_report = []
        print('>> Video processing started...')
        while cap.isOpened() and (not self.stop_event):
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            self.current_frame = frame_count
            if frame_count % self.stride != 0:
                continue
            frame_index += 1
            self.pause_event.wait()
            if self.stop_event:
                break
            start_t = time.time()
            results = self.model.track(frame, conf=self.conf, imgsz=self.imgsz, persist=True, verbose=False, tracker=self.tracker)
            res = results[0]
            annotated_frame = res.plot(labels=False)
            if self.use_roi and self.roi_polygon:
                import numpy as np
                pts = np.array(self.roi_polygon, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(annotated_frame, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
                x_org = int(self.roi_polygon[0][0])
                y_org = int(self.roi_polygon[0][1] - 10)
                cv2.putText(annotated_frame, 'RESTRICTED ZONE', (x_org, y_org), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            new_current_objects = {}
            current_ids_in_frame = set()
            if res.boxes.conf is not None:
                self.all_confs.extend(res.boxes.conf.cpu().numpy().tolist())
            if res.boxes.id is not None:
                boxes = res.boxes.xyxy.cpu().numpy().astype(int)
                ids = res.boxes.id.cpu().numpy().astype(int)
                cls_indices = res.boxes.cls.cpu().numpy().astype(int)
                names = self.model.names
                for i, (box, track_id, cls_idx) in enumerate(zip(boxes, ids, cls_indices)):
                    x1, y1, x2, y2 = box
                    current_ids_in_frame.add(track_id)
                    if self.use_tracking_trace:
                        center = (int((x1 + x2) / 2), int((y1 + y2) / 2))
                        if track_id not in self.track_history:
                            self.track_history[track_id] = []
                        self.track_history[track_id].append(center)
                        if len(self.track_history[track_id]) > 30:
                            self.track_history[track_id].pop(0)
                        points = self.track_history[track_id]
                        for j in range(1, len(points)):
                            thickness = int(1 + j / len(points) * 3)
                            cv2.line(annotated_frame, points[j - 1], points[j], (0, 255, 0), thickness)
                    class_name = names[cls_idx]
                    class_short_map = {'fishing_boat': 'F', 'speed_boat': 'S', 'passenger': 'P', 'passenger_ship': 'P'}
                    short_class = class_short_map.get(class_name.lower(), class_name[0].upper())
                    cx_point = int((x1 + x2) / 2)
                    cy_point = int((y1 + y2) / 2)
                    inside_roi = False
                    if self.roi_polygon and len(self.roi_polygon) >= 3:
                        from src.utils.geometry_utils import is_point_in_polygon
                        inside_roi = is_point_in_polygon(cx_point, cy_point, self.roi_polygon)
                        if inside_roi:
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                            cv2.putText(annotated_frame, '!! XAM NHAP VUNG CAM !!', (x1, y2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
                            if track_id not in self.violating_ids:
                                self.violating_ids.add(track_id)
                                print(f'⚠️ [CẢNH BÁO] Tàu track_id={track_id} xâm nhập vùng cấm! Tọa độ: ({cx_point}, {cy_point})')
                                try:
                                    sql_logger = get_sql_logger(self.output_folder)
                                    unique_id = f'{self.session_id}_{track_id}'
                                    loai_tau = class_name
                                    so_hieu = ''
                                    do_tin_cay_ocr = 0.0
                                    hinh_anh = ''
                                    if track_id in self.current_objects:
                                        obj = self.current_objects[track_id]
                                        loai_tau = obj.get('class_name', '') or class_name
                                    if sql_logger.get_log_by_track_id(int(track_id), self.session_id) is None:
                                        h_frm, w_frm, _ = frame.shape
                                        crop_for_alert = frame[max(0, y1):min(h_frm, y2), max(0, x1):min(w_frm, x2)].copy()
                                        self.log_new_ship(track_id, class_name, crop_for_alert, inside_roi=True)
                                    log_row = sql_logger.get_log_by_track_id(int(track_id), self.session_id)
                                    if log_row:
                                        loai_tau = log_row.get('class_name') or loai_tau
                                        hinh_anh = log_row.get('hinh_anh_path') or ''
                                    sql_logger.update_ghi_chu(unique_id, '[CẢNH BÁO XÂM NHẬP]')
                                    alert_logged = sql_logger.log_violation_alert(unique_id=unique_id, track_id=track_id, session_id=self.session_id, center_x=cx_point, center_y=cy_point, loai_tau=loai_tau, so_hieu=so_hieu, do_tin_cay_ocr=do_tin_cay_ocr, telegram_sent=False, hinh_anh=hinh_anh, ghi_chu='Tàu xâm nhập vùng cấm (ROI)')
                                    if not alert_logged:
                                        self.violating_ids.discard(track_id)
                                    elif self.on_violation_alert:
                                        try:
                                            self.on_violation_alert(track_id)
                                        except Exception:
                                            pass
                                except Exception as e:
                                    print(f'>> Error logging violation alert: {e}')
                                    self.violating_ids.discard(track_id)
                                    pass
                    crop_to_use = None
                    if track_id not in self.current_objects:
                        h_frm, w_frm, _ = frame.shape
                        cy1, cy2 = (max(0, y1), min(h_frm, y2))
                        cx1, cx2 = (max(0, x1), min(w_frm, x2))
                        crop_to_use = frame[cy1:cy2, cx1:cx2].copy()
                        self.log_new_ship(track_id, class_name, crop_to_use, inside_roi=inside_roi)
                    else:
                        crop_to_use = self.current_objects[track_id]['crop']
                    text_display = self.ocr_cache.get(track_id, {}).get('final', '...')
                    new_current_objects[track_id] = {'bbox': (x1, y1, x2, y2), 'ocr': text_display, 'crop': crop_to_use, 'class_name': class_name}
                    short_label = f'id:{track_id} {short_class} {res.boxes.conf[i]:.2f}'
                    if inside_roi:
                        short_label += ' [VIOLATION]'
                    cv2.putText(annotated_frame, short_label, (x1 + 5, y1 - 35 if text_display != '...' else y1 - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255) if inside_roi else (255, 255, 255), 2)
                    if text_display != '...':
                        cv2.putText(annotated_frame, text_display, (x1, y1 - 10), cv2.FONT_HERSHEY_COMPLEX, 0.8, (0, 0, 255) if inside_roi else (0, 255, 255), 2)
            self.current_objects = new_current_objects
            try:
                sql_logger = get_sql_logger(self.output_folder)
                conf_arr = res.boxes.conf.cpu().numpy() if res.boxes.conf is not None else None
                for i2, (tid2, obj2) in enumerate(new_current_objects.items()):
                    cx = int((obj2['bbox'][0] + obj2['bbox'][2]) / 2)
                    cy = int((obj2['bbox'][1] + obj2['bbox'][3]) / 2)
                    conf_val = float(conf_arr[i2]) if conf_arr is not None and i2 < len(conf_arr) else None
                    sql_logger.log_trajectory(unique_id=f'{self.session_id}_{tid2}', session_id=self.session_id, track_id=int(tid2), frame_index=frame_index, center_x=cx, center_y=cy, bbox_x1=int(obj2['bbox'][0]), bbox_y1=int(obj2['bbox'][1]), bbox_x2=int(obj2['bbox'][2]), bbox_y2=int(obj2['bbox'][3]), confidence=conf_val)
            except Exception as _e:
                pass
            if out is not None:
                out.write(annotated_frame)
            process_ms = (time.time() - start_t) * 1000
            fps = 1000.0 / process_ms if process_ms > 0 else 0
            update_gui_callback(annotated_frame, fps)
            data_report.append({'Frame': frame_count, 'FPS': fps, 'Objects': len(current_ids_in_frame), 'Time_ms': process_ms})
        print('>> Processing finished.')
        cap.release()
        if out is not None:
            out.release()
        if data_report:
            processed_count = len(data_report)
            total_frames = frame_count
            ocr_data = {}
            for tid, info in self.ocr_cache.items():
                final_text = info.get('final')
                if final_text and final_text != '...':
                    ocr_data[tid] = final_text
            video_name = os.path.basename(self.input_source)
            model_name = os.path.basename(self.model_path)
            txt_path, _ = save_test_report(data=data_report, all_confs=self.all_confs, output_folder=self.output_folder, video_name=video_name, processed_count=processed_count, total_frames=total_frames, model_name=model_name, imgsz=self.imgsz, stride=self.stride, conf_thresh=self.conf, tag='AUTO_TEST', ocr_data=ocr_data)
            print('>> Báo cáo đã được tạo và lưu vào thư mục output.')
            if on_done_callback and txt_path:
                on_done_callback(txt_path)
        else:
            print('>> Không có dữ liệu để tạo báo cáo.')

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            return 'paused'
        else:
            self.pause_event.set()
            return 'running'

    def stop(self):
        self.pause_event.set()
        self.stop_event = True

    def check_violations_on_cached_data(self, new_roi_polygon):
        if not new_roi_polygon or len(new_roi_polygon) < 3:
            return []
        new_violations = []
        try:
            from shapely.geometry import Point, Polygon
            roi_poly = Polygon(new_roi_polygon)
        except ImportError:
            print('>> Warning: shapely not available, using ray casting instead')
            roi_poly = None
        for track_id, obj in self.current_objects.items():
            if track_id in self.violating_ids:
                continue
            center_x = obj.get('center_x')
            center_y = obj.get('center_y')
            if center_x is None or center_y is None:
                bbox = obj.get('bbox', (0, 0, 0, 0))
                center_x = (bbox[0] + bbox[2]) // 2
                center_y = (bbox[1] + bbox[3]) // 2
            is_inside = False
            if roi_poly:
                is_inside = roi_poly.contains(Point(center_x, center_y))
            else:
                is_inside = self._point_in_polygon(center_x, center_y, new_roi_polygon)
            if is_inside:
                new_violations.append({'track_id': track_id, 'center_x': center_x, 'center_y': center_y, 'obj': obj})
                self.violating_ids.add(track_id)
        return new_violations

    def _point_in_polygon(self, x, y, polygon):
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = (p2x, p2y)
        return inside
