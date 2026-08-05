# Lab 2 — OpenCV Image Processing API (Flask)

A small Flask REST API that wraps four OpenCV image transforms:
`/gray`, `/blur`, `/edges`, `/contours`.

## 1. Setup

```bash
cd 1.OpevCVAsAPI
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Generate a test image (optional — sample.jpg is already included)

```bash
python generate_sample_image.py
```

Draws a square, a circle, and a triangle on a white canvas — good for clearly
demonstrating edge detection and contours.

## 3. Run the server

**Locally (this machine):**

```bash
python app.py
```

Runs on `http://localhost:5000` by default. Port 5000 sometimes conflicts with
macOS's AirPlay Receiver — if so, run `PORT=5001 python app.py` instead, or turn off
AirPlay Receiver in System Settings → General → AirDrop & Handoff.

**On the assigned SSH lab machine:**

Each container has a dedicated SSH port; the app ports are derived from it
(see the table below, from the assignment slides). Pick one of your five app ports
and export it before running:

| Service      | Port rule | Example (SSH = 2210) |
|--------------|-----------|-----------------------|
| SSH          | 2200      | 2210                  |
| Application 1| 3000      | 3210                  |
| Application 2| 4000      | 4210                  |
| Application 3| 5000      | 5210                  |
| Application 4| 6000      | 6210                  |
| Application 5| 7000      | 7210                  |

```bash
ssh <user>@<host> -p <your-ssh-port>
git clone <your-repo-url>
cd 1.OpevCVAsAPI
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
PORT=<your-app-port> python app.py
```

Then in Postman (or curl) hit `http://<hostname>:<your-app-port>/<route>`.

## 4. API Reference

All processing routes are `POST`, take a single multipart form-data field named
**`image`** (the file to process), and return the processed image as a raw JPEG
(`Content-Type: image/jpeg`). A missing `image` field returns `400` with a JSON
error body.

| Method | Route        | Body (form-data)   | Response                              |
|--------|--------------|---------------------|----------------------------------------|
| GET    | `/`          | —                   | JSON — API info / route list           |
| POST   | `/gray`      | `image`: file       | JPEG — grayscale                       |
| POST   | `/blur`      | `image`: file       | JPEG — Gaussian blurred (15×15 kernel) |
| POST   | `/edges`     | `image`: file       | JPEG — Canny edges (thresholds 50,150) |
| POST   | `/contours`  | `image`: file       | JPEG — original image with contours drawn in green |

## 5. Testing with curl

A ready-made script runs all four routes and saves outputs to `output/`:

```bash
./test_api.sh                       # defaults to http://localhost:5000
./test_api.sh http://localhost:5001 # or point at a different host/port
```

Equivalent manual commands:

```bash
curl -X POST -F "image=@sample.jpg" http://localhost:5000/gray     -o output/gray_output.jpg
curl -X POST -F "image=@sample.jpg" http://localhost:5000/blur     -o output/blur_output.jpg
curl -X POST -F "image=@sample.jpg" http://localhost:5000/edges    -o output/edges_output.jpg
curl -X POST -F "image=@sample.jpg" http://localhost:5000/contours -o output/contours_output.jpg

# Sanity check the JSON info route
curl http://localhost:5000/

# Error case: no file attached -> 400 JSON error
curl -X POST http://localhost:5000/gray
```

## 6. Testing with Postman

For each of `/gray`, `/blur`, `/edges`, `/contours`:

1. Create a new request, method **POST**.
2. URL: `http://<host>:<port>/<route>` (e.g. `http://localhost:5000/gray`).
3. Go to the **Body** tab → select **form-data**.
4. Add a key named `image`, change its type from *Text* to **File** (dropdown on
   the right of the key field), and choose `sample.jpg` (or any image) as the value.
5. Click **Send**.
6. The response preview shows the processed image. Status should be `200 OK` with
   header `Content-Type: image/jpeg`.
7. To save it: click the **Save Response** dropdown (next to Send) → **Save to a
   file**.
8. Screenshot the request+response for the report and save it into
   `postman_screenshots/` as `gray.png`, `blur.png`, `edges.png`, `contours.png`.

To verify the error handling, send a POST to `/gray` with an empty Body — you
should get `400` and a JSON error message.

## 7. Project files

```
app.py                      Flask application (4 routes + home route)
generate_sample_image.py    Creates the synthetic sample.jpg test input
sample.jpg                  Test input image
test_api.sh                 curl smoke-test script for all routes
output/                     curl-generated output images
postman_screenshots/        Postman screenshots go here (see PLACEHOLDER.md)
report/Lab2_Report.html     Submission report (open in browser -> Print -> Save as PDF)
requirements.txt            Python dependencies
```
