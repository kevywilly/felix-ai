import cv2, time

GST = ("nvarguscamerasrc sensor-id=0 ! "
       "video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! "
       "nvvidconv ! video/x-raw, width=640, height=360, format=BGRx ! "
       "videoconvert ! video/x-raw, format=BGR ! "
       "appsink drop=1 max-buffers=1")

cap = cv2.VideoCapture(GST, cv2.CAP_GSTREAMER)
print("opened:", cap.isOpened())

t0, n = time.time(), 0
while n < 100:
    ok, frame = cap.read()
    if not ok:
        print("read failed at frame", n); break
    n += 1
print(f"{n} frames in {time.time()-t0:.2f}s, shape={frame.shape}")
cv2.imwrite("/tmp/test.jpg", frame)
