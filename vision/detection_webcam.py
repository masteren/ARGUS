from ultralytics import YOLO
import cv2
import time
import os
import threading
import requests
import base64
from datetime import datetime

# ── Backend (B) ──────────────────────────────────────────────
# B (ARGUS_backend/app.py) tourne sur le port 5000.
#   ・B sur la même machine   → "http://localhost:5000"
#   ・B sur une autre machine  → "http://<IP LAN de B>:5000"
# Le port est surchargeable par la variable d'environnement PORT (même variable
# que B/app.py). Défaut = 5000, conforme au contrat. Sur macOS, AirPlay occupe
# 5000 : lancer les tests d'intégration avec PORT=5001.
B_PORT     = os.environ.get("PORT", "5000")
B_URL      = "http://localhost:%s" % B_PORT
UPLOAD_URL = f"{B_URL}/upload"                 # 【CORRIGÉ】était /detection

# ── Source caméra (DÉCISION 2 = option 1 : seul B ouvre la caméra) ──────────
# On NE fait PAS cv2.VideoCapture(0) ici : B possède la caméra et sert /video_feed.
# A tire les frames depuis le flux de B → plus de conflit sur /dev/video0.
# Pour tester en local sans B, remettre CAMERA_SOURCE = 0 (webcam directe).
CAMERA_SOURCE = f"{B_URL}/video_feed"          # option 1 ; mettre 0 pour une webcam locale

# ── Déclencheur de mission « search_person » (CONTRACT.md ①) ───────────────
# Quand un spectateur paie search_person, B crée une mission `active`.
# A consulte `GET /mission/active` (et non /commands : C consomme la commande et
# la passe à `done` en quelques secondes, la fenêtre serait trop courte pour A).
# Tant que la mission est active, la première personne détectée est envoyée avec
# type="mission_person" → B bascule la mission en `success`.
MISSION_URL           = f"{B_URL}/mission/active"
MISSION_POLL_INTERVAL = 2.0
MISSION_TYPE          = "mission_person"

mission_active   = False    # écrit par le thread de veille, lu par la boucle vidéo
mission_reported = False    # évite de spammer B une fois la mission remplie


def suivre_mission():
    """Thread de fond : tient `mission_active` à jour depuis B."""
    global mission_active, mission_reported
    while True:
        try:
            payload = requests.get(MISSION_URL, timeout=3).json()
            actif = bool(payload.get("active"))
            if actif and not mission_active:
                print("[MISSION] search_person payé → détection de mission ARMÉE", flush=True)
                mission_reported = False
            elif mission_active and not actif:
                print("[MISSION] mission terminée → retour au mode normal", flush=True)
            mission_active = actif
        except Exception as e:
            # B indisponible : on garde l'état précédent et on réessaie
            print(f"[MISSION] backend injoignable : {e}", flush=True)
        time.sleep(MISSION_POLL_INTERVAL)


# Anti-spam / throttle des POST
SEUIL_INITIAL   = 0.40
SEUIL_INCREMENT = 0.10
MAX_ALERTES     = 5
FRAMES_REQUIS   = 3
WARMUP          = 2
CONF_MIN_POST   = 0.50
POST_INTERVAL   = 3.0
CLASSES_POST    = {"person"}
dernier_post    = 0

model = YOLO("yolov8n_ncnn_model")

mode             = "normal"
nom_cible        = None
hist_cible       = None
nb_alertes       = 0
prochain_seuil   = SEUIL_INITIAL
frames_positifs  = 0
temps_chargement = 0
dernier_log_fps  = 0


def histogramme(image):
    img = cv2.resize(image, (256, 256))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def comparer(h1, h2):
    return max(0, cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL))


# ── POST vers B ──────────────────────────────────────────────
# 【CORRIGÉ】Contrat réel de B : /upload, champs {timestamp, type, confidence, image}.
# 【HUD navigateur — DÉCISION 2】on ajoute aussi bbox [x1,y1,x2,y2] et frame_wh
#   pour que la page publique dessine la boîte par-dessus le flux (overlay côté navigateur).
#   ⚠️ B doit exposer ces champs via /events (ou un /overlay dédié) — voir CONTRACT.md (TODO B).
def envoyer_detection(image, detection_type, confidence, bbox=None):
    _, buffer = cv2.imencode('.jpg', image)
    image_b64 = base64.b64encode(buffer).decode('utf-8')
    payload = {
        "timestamp":  datetime.now().isoformat(timespec="seconds"),
        "type":       detection_type,
        "confidence": round(float(confidence), 2),
        "image":      image_b64,
    }
    if bbox is not None:
        h, w = image.shape[:2]
        payload["bbox"] = [int(v) for v in bbox]     # [x1,y1,x2,y2] en pixels
        payload["frame_wh"] = [w, h]
    try:
        r = requests.post(UPLOAD_URL, json=payload, timeout=2)
        print(f"[POST] /upload {detection_type} {confidence:.2f} -> {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"[POST] Backend indisponible : {e}")
        return False


def prendre_screenshot(frame, sim):
    global nb_alertes, prochain_seuil, mode
    nb_alertes += 1
    prochain_seuil += SEUIL_INCREMENT
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cv2.imwrite(f"detection_{ts}.jpg", frame)
    print(f"[TARGET] {nom_cible} — {sim:.0%} | {nb_alertes}/{MAX_ALERTES}", flush=True)
    envoyer_detection(frame, f"mission_{nom_cible or 'target'}", sim)
    if nb_alertes >= MAX_ALERTES:
        mode = "normal"


# Veille des missions payées, en tâche de fond (daemon : s'arrête avec le script)
threading.Thread(target=suivre_mission, daemon=True).start()

cap = cv2.VideoCapture(CAMERA_SOURCE)
fps_t = time.time()
print(f"Flux démarré depuis {CAMERA_SOURCE} — Ctrl+C pour quitter", flush=True)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        now = time.time()
        fps = 1 / (now - fps_t) if now != fps_t else 0
        fps_t = now

        if mode == "normal":
            results = model(frame, verbose=False)
            # 【chemin A→B branché】on remonte les détections person à B (throttlé).
            for box in results[0].boxes:
                nom_classe = model.names[int(box.cls[0])]
                conf = float(box.conf[0])
                if nom_classe in CLASSES_POST and conf >= CONF_MIN_POST:
                    if mission_active and not mission_reported:
                        # Mission payée en cours : on remonte tout de suite, sans
                        # throttle, avec le préfixe qui déclenche `success` chez B.
                        # On ne marque « rapportée » que si B a bien reçu : sinon la
                        # mission resterait active pour toujours sans nouvelle tentative.
                        mission_reported = envoyer_detection(
                            frame, MISSION_TYPE, conf, bbox=box.xyxy[0].tolist()
                        )
                        dernier_post = now
                    elif now - dernier_post >= POST_INTERVAL:
                        envoyer_detection(frame, nom_classe, conf, bbox=box.xyxy[0].tolist())
                        dernier_post = now
                    break

            if now - dernier_log_fps >= 10:
                etat = "MISSION" if mission_active else "NORMAL"
                print(f"FPS: {fps:.1f} | MODE: {etat}", flush=True)
                dernier_log_fps = now

        elif mode == "recherche":
            if now - temps_chargement < WARMUP:
                frames_positifs = 0
            else:
                sim = comparer(hist_cible, histogramme(frame))
                frames_positifs = frames_positifs + 1 if sim >= prochain_seuil else 0
                if frames_positifs >= FRAMES_REQUIS:
                    prendre_screenshot(frame, sim)
                    frames_positifs = 0

except KeyboardInterrupt:
    print("Arrêt.")

cap.release()
