from ultralytics import YOLO
import cv2
import time
import requests
import base64
from datetime import datetime

# --- Config ---
SEUIL_INITIAL   = 0.40
SEUIL_INCREMENT = 0.10
MAX_ALERTES     = 5
FRAMES_REQUIS   = 3
WARMUP          = 2

model = YOLO("yolov8n_ncnn_model")

mode             = "normal"
nom_cible        = None
hist_cible       = None
nb_alertes       = 0
prochain_seuil   = SEUIL_INITIAL
frames_positifs  = 0
temps_chargement = 0
dernier_log_fps  = 0  # timestamp du dernier affichage FPS

def histogramme(image):
    img = cv2.resize(image, (256, 256))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
    cv2.normalize(hist, hist)
    return hist

def comparer(h1, h2):
    return max(0, cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL))

def envoyer_post(image, sim):
    _, buffer = cv2.imencode('.jpg', image)
    image_b64 = base64.b64encode(buffer).decode('utf-8')
    payload = {
        "mission_id": "test_local",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": nom_cible,
        "similarite": round(sim, 2),
        "image": image_b64
    }
    try:
        requests.post("http://localhost:5000/detection", json=payload, timeout=2)
        print("[POST] Envoyé au backend")
    except Exception as e:
        print(f"[POST] Backend indisponible : {e}")

def prendre_screenshot(frame, sim):
    global nb_alertes, prochain_seuil, mode
    nb_alertes += 1
    prochain_seuil += SEUIL_INCREMENT
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fichier = f"detection_{ts}.jpg"
    cv2.imwrite(fichier, frame)
    print(f"[TARGET] {nom_cible} — {sim:.0%} | screenshot {nb_alertes}/{MAX_ALERTES} | prochain seuil : {prochain_seuil:.0%}", flush=True)
    envoyer_post(frame, sim)
    if nb_alertes >= MAX_ALERTES:
        print(f"[INFO] {MAX_ALERTES} screenshots atteints — retour mode normal", flush=True)
        mode = "normal"

cap = cv2.VideoCapture(0)
fps_t = time.time()
print("Flux démarré — Ctrl+C pour quitter", flush=True)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        now = time.time()
        fps = 1 / (now - fps_t)
        fps_t = now

        if mode == "normal":
            results = model(frame, verbose=False)
            if now - dernier_log_fps >= 10:
                print(f"FPS: {fps:.1f} | MODE: NORMAL", flush=True)
                dernier_log_fps = now

        elif mode == "recherche":
            if now - temps_chargement < WARMUP:
                frames_positifs = 0
            else:
                sim = comparer(hist_cible, histogramme(frame))
                if sim >= prochain_seuil:
                    frames_positifs += 1
                else:
                    frames_positifs = 0
                if frames_positifs >= FRAMES_REQUIS:
                    prendre_screenshot(frame, sim)
                    frames_positifs = 0
                if now - dernier_log_fps >= 10:
                    print(f"FPS: {fps:.1f} | {sim:.0%} | prochain: {prochain_seuil:.0%} | {nb_alertes}/{MAX_ALERTES}", flush=True)
                    dernier_log_fps = now

except KeyboardInterrupt:
    print("Arrêt.")

cap.release()