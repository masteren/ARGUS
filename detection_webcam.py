from ultralytics import YOLO
import cv2
import time

fps_precedent = time.time()

model = YOLO("yolov8n.pt")

cap = cv2.VideoCapture(0)
print("Détection en cours. Appuie sur 'q' pour quitter.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, verbose=False)
    result = results[0]

    maintenant = time.time()
    fps = 1 / (maintenant - fps_precedent)
    fps_precedent = maintenant

    for box in result.boxes:
        classe_id = int(box.cls[0])
        nom_classe = model.names[classe_id]
        confiance = float(box.conf[0])

        if nom_classe == "person" and confiance > 0.5:
            print(f"[DÉTECTION] personne détectée — confiance : {confiance:.2f}")

    image_annotee = result.plot()

    cv2.putText(image_annotee, f"FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("ARGUS — Détection", image_annotee)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()