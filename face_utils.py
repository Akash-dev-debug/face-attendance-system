import cv2
import numpy as np
import os
import base64

DATASET_DIR = "static/dataset"
TRAINER_PATH = "trainer/trainer.yml"

CASCADE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "haarcascade_frontalface_default.xml")
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)

if face_cascade.empty():
    raise RuntimeError(
        f"Could not load face cascade from {CASCADE_PATH}. "
        "Make sure haarcascade_frontalface_default.xml is in the project folder."
    )


def decode_base64_image(data_url):
    """Convert a base64 image string (from the browser webcam) into an OpenCV image."""
    header, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img


def detect_largest_face(img):
    """Returns the cropped grayscale face (largest one found) and its box, or (None, None)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80))
    if len(faces) == 0:
        return None, None
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    (x, y, w, h) = faces[0]
    face_crop = gray[y:y + h, x:x + w]
    face_crop = cv2.resize(face_crop, (200, 200))
    return face_crop, (int(x), int(y), int(w), int(h))


def save_face_sample(user_id, face_gray_img, index):
    user_dir = os.path.join(DATASET_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, f"{index}.jpg")
    cv2.imwrite(path, face_gray_img)


def train_model():
    """Rebuilds the trained model from every saved face sample of every user."""
    faces = []
    labels = []

    if not os.path.exists(DATASET_DIR):
        return 0, 0

    for user_id_str in os.listdir(DATASET_DIR):
        user_dir = os.path.join(DATASET_DIR, user_id_str)
        if not os.path.isdir(user_dir):
            continue
        try:
            user_id = int(user_id_str)
        except ValueError:
            continue
        for filename in os.listdir(user_dir):
            if filename.lower().endswith((".jpg", ".png")):
                path = os.path.join(user_dir, filename)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    faces.append(img)
                    labels.append(user_id)

    if len(faces) == 0:
        return 0, 0

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels))
    os.makedirs("trainer", exist_ok=True)
    recognizer.write(TRAINER_PATH)
    return len(set(labels)), len(faces)


_recognizer = None


def get_recognizer():
    global _recognizer
    if _recognizer is None:
        if not os.path.exists(TRAINER_PATH):
            return None
        _recognizer = cv2.face.LBPHFaceRecognizer_create()
        _recognizer.read(TRAINER_PATH)
    return _recognizer


def reload_recognizer():
    global _recognizer
    _recognizer = None


def recognize_face(face_gray_img, threshold=48):
    """Returns (user_id, confidence) if recognized within threshold, else (None, confidence)."""
    recognizer = get_recognizer()
    if recognizer is None:
        return None, None
    label, confidence = recognizer.predict(face_gray_img)
    # LBPH confidence is a distance: LOWER means a better match.
    if confidence <= threshold:
        return label, confidence
    return None, confidence