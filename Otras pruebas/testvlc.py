import cv2

# --- URL a probar ---
rtsp_url = "rtsp://FAC_ElGaraje:santi002@192.168.0.103:554/stream1"

print("Intentando conectar con OpenCV a:", rtsp_url)
cap = cv2.VideoCapture(rtsp_url)

# Verificar si la conexión fue exitosa
if not cap.isOpened():
    print("!!! ERROR: No se pudo abrir el stream con OpenCV.")
    exit()

print("¡Conexión exitosa! Mostrando video. Presiona 'q' para salir.")

while True:
    # Leer un frame del video
    ret, frame = cap.read()

    # Si 'ret' es False, significa que no se pudo leer el frame
    if not ret:
        print("!!! ERROR: Fallo al leer frame del stream. Se ha perdido la conexión.")
        break

    # Mostrar el frame en una ventana
    cv2.imshow('Prueba OpenCV', frame)
    print("-> Frame recibido y mostrado correctamente.")

    # Romper el bucle si se presiona la tecla 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Liberar la cámara y destruir todas las ventanas
print("Cerrando stream...")
cap.release()
cv2.destroyAllWindows()