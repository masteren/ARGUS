from ultralytics import YOLO
import cv2
import time
import tkinter as tk
from tkinter import filedialog
import requests
import base64
import winsound
from datetime import datetime

# --- Config ---
SEUIL_INITIAL   = 0.40   # premier screenshot à 40%
SEUIL_INCREMENT = 0.10   # +10% pour chaque screenshot suivant
MAX_ALERTES     = 5      # 40% → 50% → 60% → 70% → 80% = 5 screenshots max
FRAMES_REQUIS   = 3      # frames consécutifs pour confirmer avant screenshot
WARMUP          = 2      # secondes d'attente après chargement

model = YOLO("yolov8n.pt")

mode             = "normal"
nom_cible        = None
hist_cible       = None
nb_alertes       = 0
prochain_seuil   = SEUIL_INITIAL   # seuil du prochain screenshot
frames_positifs  = 0
temps_chargement = 0

def selectionner_image():
    root = tk.Tk()
    root.withdraw()
    chemin = filedialog.askopenfilename(
        title="Sélectionner une image cible",
        filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp")]
    )
    root.destroy()
    return chemin

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
    print(f"[TARGET] {nom_cible} — {sim:.0%} | screenshot {nb_alertes}/{MAX_ALERTES} | prochain seuil : {prochain_seuil:.0%}")
    try:
        winsound.Beep(1000, 300)
    except:
        pass
    envoyer_post(frame, sim)

    # Max atteint → retour automatique en mode normal
    if nb_alertes >= MAX_ALERTES:
        print(f"[INFO] {MAX_ALERTES} screenshots atteints — retour automatique en mode normal")
        mode = "normal"

cap = cv2.VideoCapture(0)
fps_t = time.time()
print("Flux démarré | 'u' charger cible | 'n' mode normal | 'q' quitter")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    now = time.time()
    fps = 1 / (now - fps_t)
    fps_t = now

    # ── MODE NORMAL ───────────────────────────────────────────────
    if mode == "normal":
        results = model(frame, verbose=False)
        image_annotee = results[0].plot()
        cv2.putText(image_annotee, "MODE: NORMAL", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # ── MODE RECHERCHE ────────────────────────────────────────────
    elif mode == "recherche":
        image_annotee = frame.copy()

        if now - temps_chargement < WARMUP:
            restant = WARMUP - (now - temps_chargement)
            cv2.putText(image_annotee, f"Preparation... {restant:.1f}s", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
            frames_positifs = 0

        else:
            sim = comparer(hist_cible, histogramme(frame))

            # Frame positif si au-dessus du prochain seuil
            if sim >= prochain_seuil:
                frames_positifs += 1
                couleur = (0, 255, 0)
            else:
                frames_positifs = 0
                couleur = (0, 255, 255)

            # Déclenche screenshot après FRAMES_REQUIS frames consécutifs
            if frames_positifs >= FRAMES_REQUIS:
                prendre_screenshot(frame, sim)
                frames_positifs = 0

            cv2.putText(image_annotee,
                        f"RECHERCHE: {nom_cible} | {sim:.0%} | prochain: {prochain_seuil:.0%} | {nb_alertes}/{MAX_ALERTES} | frames: {frames_positifs}/{FRAMES_REQUIS}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, couleur, 2)

    cv2.putText(image_annotee, f"FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.imshow("ARGUS", image_annotee)

    touche = cv2.waitKey(1) & 0xFF

    if touche == ord('q'):
        break

    elif touche == ord('u'):
        # Reset complet avant ouverture du dialogue
        hist_cible      = None
        mode            = "normal"
        nb_alertes      = 0
        prochain_seuil  = SEUIL_INITIAL
        frames_positifs = 0

        chemin = selectionner_image()
        if chemin:
            img              = cv2.imread(chemin)
            nom_cible        = chemin.split("/")[-1]
            hist_cible       = histogramme(img)
            mode             = "recherche"
            temps_chargement = time.time()
            print(f"[RECHERCHE] Cible : {nom_cible} | premier seuil : {prochain_seuil:.0%}")

    elif touche == ord('n'):
        mode            = "normal"
        hist_cible      = None
        nom_cible       = None
        nb_alertes      = 0
        prochain_seuil  = SEUIL_INITIAL
        frames_positifs = 0
        print("[NORMAL]")

cap.release()
cv2.destroyAllWindows()