import os

from flask import Flask, request, Response, jsonify
import cv2
import numpy as np

app = Flask(__name__)


def decode_image(file_storage):
    data = np.frombuffer(file_storage.read(), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def encode_image(img):
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def require_image():
    if "image" not in request.files:
        return None, (jsonify({"error": "No 'image' file part in request"}), 400)
    img = decode_image(request.files["image"])
    if img is None:
        return None, (jsonify({"error": "Uploaded file is not a valid image"}), 400)
    return img, None


@app.route("/")
def home():
    return jsonify({
        "message": "OpenCV Image Processing API",
        "routes": {
            "/gray": "POST form-data 'image' -> grayscale JPEG",
            "/blur": "POST form-data 'image' -> Gaussian-blurred JPEG",
            "/edges": "POST form-data 'image' -> Canny edge-detected JPEG",
            "/contours": "POST form-data 'image' -> JPEG with contours drawn",
        },
    })


@app.route("/gray", methods=["POST"])
def gray():
    img, err = require_image()
    if err:
        return err

    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return Response(encode_image(gray_img), mimetype="image/jpeg")


@app.route("/blur", methods=["POST"])
def blur():
    img, err = require_image()
    if err:
        return err

    blurred = cv2.GaussianBlur(img, (15, 15), 0)
    return Response(encode_image(blurred), mimetype="image/jpeg")


@app.route("/edges", methods=["POST"])
def edges():
    img, err = require_image()
    if err:
        return err

    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edge_img = cv2.Canny(gray_img, 50, 150)
    return Response(encode_image(edge_img), mimetype="image/jpeg")


@app.route("/contours", methods=["POST"])
def contours():
    img, err = require_image()
    if err:
        return err

    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edge_img = cv2.Canny(gray_img, 50, 150)
    cnts, _ = cv2.findContours(edge_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    output = img.copy()
    cv2.drawContours(output, cnts, -1, (0, 255, 0), 2)
    return Response(encode_image(output), mimetype="image/jpeg")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
