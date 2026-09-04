import cv2

cap = cv2.VideoCapture(0)

print("Flux caméra ouvert. Appuie sur 'q' pour quitter.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    cv2.imshow("Test caméra ARGUS", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Flux fermé proprement.")