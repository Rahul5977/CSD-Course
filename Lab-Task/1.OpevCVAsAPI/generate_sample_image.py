import cv2
import numpy as np

canvas = np.full((480, 640, 3), 255, dtype=np.uint8)

cv2.rectangle(canvas, (60, 80), (260, 280), (255, 120, 0), thickness=-1)
cv2.circle(canvas, (450, 180), 100, (0, 180, 0), thickness=-1)

triangle = np.array([[320, 400], [200, 440], [440, 440]], dtype=np.int32)
cv2.fillPoly(canvas, [triangle], (0, 0, 220))

cv2.imwrite("sample.jpg", canvas)
print("Wrote sample.jpg")
