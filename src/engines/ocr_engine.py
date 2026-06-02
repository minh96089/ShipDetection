import cv2
import logging
import numpy as np
from paddleocr import PaddleOCR
logging.getLogger('ppocr').setLevel(logging.WARNING)

class ShipOCR:

    def __init__(self, lang='en', use_angle_cls=True):
        print('Loading PaddleOCR...')
        self.ocr = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang)
        print('PaddleOCR ready')

    def _preprocess_text_crop(self, text_crop):
        """Tiền xử lý ảnh vùng chữ trước khi đưa vào OCR:
        scale up → bilateral filter → CLAHE → sharpen."""
        if text_crop is None or text_crop.size == 0:
            return None
        try:
            height, width = text_crop.shape[:2]
            # Scale up mạnh hơn nếu ảnh nhỏ
            scale_factor = 3 if height < 50 else 2
            text_crop = cv2.resize(
                text_crop,
                (width * scale_factor, height * scale_factor),
                interpolation=cv2.INTER_CUBIC,
            )
            # Chuyển xám → giảm nhiễu
            gray = cv2.cvtColor(text_crop, cv2.COLOR_BGR2GRAY)
            denoised = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
            # Tăng tương phản cục bộ (CLAHE)
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            # Làm nét cạnh
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)
            # Trả về BGR để PaddleOCR xử lý bình thường
            return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
        except Exception as e:
            print(f'>> Lỗi tiền xử lý ảnh text: {e}')
            return text_crop

    def ocr_image(self, image_cv):
        """Nhận dạng văn bản từ ảnh crop. Tự động tiền xử lý trước khi OCR."""
        results = []
        # Tiền xử lý để tăng độ chính xác
        processed = self._preprocess_text_crop(image_cv)
        if processed is None:
            processed = image_cv
        ocr_result = self.ocr.ocr(processed)
        if not ocr_result or ocr_result[0] is None:
            return results
        data = ocr_result[0]
        if isinstance(data, dict):
            boxes = data.get('dt_polys', [])
            texts = data.get('rec_texts', [])
            scores = data.get('rec_scores', [])
            for box, text, score in zip(boxes, texts, scores):
                results.append({'text': text, 'score': float(score), 'box': box})
        else:
            for line in data:
                box = line[0]
                text = line[1][0]
                score = float(line[1][1])
                if score > 0.7:
                    results.append({'text': text, 'score': score, 'box': box})
        return results
