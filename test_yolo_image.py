from ultralytics import YOLO
import cv2

model = YOLO("yolov8n.pt")
print("Modèle chargé.")
print("Classes disponibles :", model.names)

cap = cv2.VideoCapture(0)
ret, frame = cap.read()
cap.release()

if not ret:
    print("ERREUR : impossible de lire la webcam")
    exit()

results = model(frame)
result = results[0]

print(f"\nNombre de détections : {len(result.boxes)}")



for i, box in enumerate(result.boxes):
    classe_id = int(box.cls[0])
    nom_classe = model.names[classe_id]
    confiance = float(box.conf[0])
    coords = box.xyxy[0].tolist()
    print(f"  Détection {i+1} : {nom_classe} | confiance : {confiance:.2f} | coords : {coords}")

image_annotee = result.plot()
cv2.imshow("Résultat YOLO", image_annotee)
cv2.waitKey(0)
cv2.destroyAllWindows()