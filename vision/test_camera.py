import cv2

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("erreur : impossible d'ouvrir la caméra")
else:
    print("Caméra détectée avec succès")

cap.release()