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

    def ocr_image(self, image_cv):
        results = []
        ocr_result = self.ocr.ocr(image_cv)
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
