# --- VISOR MULTI-CÁMARA CON DETECCIÓN DE PERROS (OpenCV + YOLO) ---

import cv2
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from PIL import Image, ImageTk
import os
import math
import time
from urllib.parse import urlparse
import numpy as np
from playsound import playsound
import sv_ttk

# --- CONFIGURACIÓN GLOBAL ---
CONFIG_FILE = "cameras.txt"
CAMS_PER_PAGE = 6
GRID_COLS = 3
CANVAS_WIDTH = 480
CANVAS_HEIGHT = 270
# --- Configuración de Detección ---
YOLO_PATH = "yolo"
CONFIDENCE_THRESHOLD = 0.5 # Sensibilidad de la detección (0.0 a 1.0)
ALERT_SOUND_FILE = "alerta.wav"
# --------------------

# (La clase SettingsDialog no cambia, la incluyo al final por completitud)
class SettingsDialog(tk.Toplevel):
    # ... (código idéntico a versiones anteriores)
    pass

# --- CLASE PRINCIPAL DE LA APLICACIÓN ---
class CameraViewerApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        
        self.all_camera_urls = self.load_urls_from_file()
        
        self.active_streams = {}; self.latest_frames = {}
        self.current_page = 0; self.total_pages = 0
        self.fullscreen_mode = False; self.fullscreen_camera_index = None
        
        self.running = True
        
        # --- NUEVO: Cargar el modelo YOLO ---
        self.yolo_net = cv2.dnn.readNetFromDarknet(os.path.join(YOLO_PATH, "yolov3-tiny.cfg"), os.path.join(YOLO_PATH, "yolov3-tiny.weights"))
        self.yolo_layers = self.yolo_net.getLayerNames()
        self.output_layers = [self.yolo_layers[i - 1] for i in self.yolo_net.getUnconnectedOutLayers()]
        with open(os.path.join(YOLO_PATH, "coco.names"), "r") as f:
            self.yolo_classes = [line.strip() for line in f.readlines()]
        
        # --- NUEVO: Hilo para la detección ---
        self.detection_thread = None
        self.detection_running = threading.Event()

        # --- UI ---
        # (El resto de la UI es igual a la versión de OpenCV)
        top_bar = ttk.Frame(self.window); top_bar.pack(side="top", fill="x", padx=10, pady=5)
        ttk.Button(top_bar, text="Administrar Cámaras", command=self.open_settings).pack(side="left")
        self.grid_frame = ttk.Frame(self.window); self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.camera_canvases = []
        self.bottom_bar = ttk.Frame(self.window); self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)
        self.prev_button = ttk.Button(self.bottom_bar, text="<< Anterior", command=self.prev_page); self.prev_button.pack(side="left")
        self.page_label = ttk.Label(self.bottom_bar, text="Página 0 de 0", anchor="center"); self.page_label.pack(side="left", fill="x", expand=True)
        self.next_button = ttk.Button(self.bottom_bar, text="Siguiente >>", command=self.next_page); self.next_button.pack(side="right")
        self.fullscreen_frame = ttk.Frame(self.window)
        self.fullscreen_label = ttk.Label(self.fullscreen_frame, text="", font=("Helvetica", 14, "bold")); self.fullscreen_label.pack(pady=(10,5))
        self.fullscreen_canvas = tk.Canvas(self.fullscreen_frame, bg="black")
        self.fullscreen_canvas.pack(fill="both", expand=True, padx=10, pady=5)
        ttk.Button(self.fullscreen_frame, text="Volver a la Cuadrícula (Esc)", command=self.exit_fullscreen).pack(pady=10)
        
        self.update_page_view()
        self.delay = 33
        self.update_gui_frames()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.mainloop()

    # --- Lógica de Detección ---
    def detect_dogs_thread(self):
        last_alert_time = 0
        while self.detection_running.is_set():
            if self.fullscreen_camera_index is None:
                time.sleep(0.5)
                continue

            frame = self.latest_frames.get(self.fullscreen_camera_index)
            if frame is None:
                time.sleep(0.5)
                continue

            # Clonar el frame para no modificar el original que se muestra
            detection_frame = frame.copy()
            height, width, _ = detection_frame.shape

            blob = cv2.dnn.blobFromImage(detection_frame, 1 / 255.0, (416, 416), swapRB=True, crop=False)
            self.yolo_net.setInput(blob)
            layer_outputs = self.yolo_net.forward(self.output_layers)

            dog_detected = False
            for output in layer_outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    if confidence > CONFIDENCE_THRESHOLD and self.yolo_classes[class_id] == "dog":
                        dog_detected = True
                        # Dibujar recuadro
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        cv2.putText(frame, "Perro Detectado", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        
            if dog_detected and (time.time() - last_alert_time) > 5: # Alerta sonora cada 5 segundos
                last_alert_time = time.time()
                try:
                    # Reproducir sonido en un hilo para no bloquear
                    threading.Thread(target=playsound, args=(ALERT_SOUND_FILE,), daemon=True).start()
                except Exception as e:
                    print(f"No se pudo reproducir el sonido de alerta: {e}")
            
            time.sleep(0.5) # Esperar un poco entre detecciones para no saturar la CPU

    # --- Modificaciones para activar/desactivar la detección ---
    def enter_fullscreen(self, global_index):
        self.fullscreen_mode = True
        self.fullscreen_camera_index = global_index
        # ... (código existente de enter_fullscreen)
        self.grid_frame.pack_forget()
        self.bottom_bar.pack_forget()
        self.fullscreen_frame.pack(fill="both", expand=True)
        self.window.bind("<Escape>", self.exit_fullscreen)
        
        # Iniciar el hilo de detección
        if not self.detection_running.is_set():
            self.detection_running.set()
            self.detection_thread = threading.Thread(target=self.detect_dogs_thread, daemon=True)
            self.detection_thread.start()
            print("--- Hilo de detección INICIADO ---")

    def exit_fullscreen(self, event=None):
        # Detener el hilo de detección
        if self.detection_running.is_set():
            self.detection_running.clear()
            if self.detection_thread:
                self.detection_thread.join(timeout=1.0)
            print("--- Hilo de detección DETENIDO ---")
            
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None
        # ... (código existente de exit_fullscreen)
        self.fullscreen_frame.pack_forget()
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)
        self.window.unbind("<Escape>")

    def on_closing(self):
        self.detection_running.clear() # Asegurarse de detener el hilo al cerrar
        self.running = False
        self.stop_all_active_streams()
        self.window.after(100, self.window.destroy)

    # --- El resto del código es de la versión de OpenCV, sin cambios mayores ---
    def _extract_name_from_url(self, url, default_name="Cámara sin nombre"):
        try: parsed_url = urlparse(url); return parsed_url.username or parsed_url.hostname or default_name
        except Exception: return default_name
    def load_urls_from_file(self):
        if not os.path.exists(CONFIG_FILE): return []
        with open(CONFIG_FILE, "r") as f: return [line.strip() for line in f if line.strip()]
    def save_urls_to_file(self):
        with open(CONFIG_FILE, "w") as f:
            for url in self.all_camera_urls: f.write(url + "\n")
    def open_settings(self):
        if self.fullscreen_mode: self.exit_fullscreen()
        dialog = SettingsDialog(self.window, self.all_camera_urls)
        if dialog.result is not None:
            self.all_camera_urls = dialog.result; self.save_urls_to_file()
            self.current_page = 0; self.update_page_view()
    def update_page_view(self):
        self.stop_all_active_streams()
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        self.camera_canvases = []
        self.num_total_cameras = len(self.all_camera_urls)
        self.total_pages = math.ceil(self.num_total_cameras / CAMS_PER_PAGE) if self.num_total_cameras > 0 else 1
        if self.current_page >= self.total_pages: self.current_page = self.total_pages - 1
        if self.current_page < 0: self.current_page = 0
        self.page_label.config(text=f"Página {self.current_page + 1} de {self.total_pages}")
        self.prev_button.config(state="normal" if self.current_page > 0 else "disabled")
        self.next_button.config(state="normal" if self.current_page < self.total_pages - 1 else "disabled")
        for i in range(GRID_COLS): self.grid_frame.grid_columnconfigure(i, weight=1)
        rows_in_page = math.ceil(CAMS_PER_PAGE / GRID_COLS)
        for i in range(rows_in_page): self.grid_frame.grid_rowconfigure(i, weight=1)
        start_index = self.current_page * CAMS_PER_PAGE
        for i in range(CAMS_PER_PAGE):
            row, col = i // GRID_COLS, i % GRID_COLS
            global_index = start_index + i
            pane = ttk.LabelFrame(self.grid_frame, text=f"CÁMARA {global_index+1}" if global_index < self.num_total_cameras else "Vacío")
            pane.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            canvas = tk.Canvas(pane, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="black")
            canvas.pack(fill="both", expand=True)
            self.camera_canvases.append(canvas)
            if global_index < self.num_total_cameras:
                url = self.all_camera_urls[global_index]
                pane.config(text=self._extract_name_from_url(url, default_name=f"CÁMARA {global_index+1}"))
                canvas.config(cursor="hand2")
                canvas.bind("<Double-1>", lambda event, idx=global_index: self.enter_fullscreen(idx))
                self.start_stream(global_index, url)
            else: canvas.config(bg="gray80")
    def start_stream(self, global_index, url):
        if url and global_index not in self.active_streams:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                flag = [True]
                thread = threading.Thread(target=self.read_frames, args=(cap, global_index, flag), daemon=True)
                self.active_streams[global_index] = (thread, cap, flag)
                thread.start()
    def read_frames(self, cap, global_index, running_flag):
        while running_flag[0]:
            ret, frame = cap.read()
            self.latest_frames[global_index] = frame if ret else None
            if not ret: time.sleep(1)
        cap.release()
    def update_gui_frames(self):
        if self.fullscreen_mode:
            frame = self.latest_frames.get(self.fullscreen_camera_index)
            canvas = self.fullscreen_canvas
            if frame is not None:
                h, w, _ = frame.shape
                canvas_w, canvas_h = canvas.winfo_width(), canvas.winfo_height()
                if canvas_w > 1 and canvas_h > 1:
                    scale = min(canvas_w / w, canvas_h / h)
                    new_w, new_h = int(w * scale), int(h * scale)
                    frame_resized = cv2.resize(frame, (new_w, new_h))
                    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    bg_image = Image.new('RGB', (canvas_w, canvas_h), 'black')
                    offset = ((canvas_w - new_w) // 2, (canvas_h - new_h) // 2)
                    bg_image.paste(img, offset)
                    photo = ImageTk.PhotoImage(image=bg_image)
                    canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                    canvas.image = photo
            else:
                canvas.delete("all")
                if canvas.winfo_width() > 1:
                    canvas.create_text(canvas.winfo_width() // 2, canvas.winfo_height() // 2, text="Sin Señal", fill="white", font=("Helvetica", 24))
        else:
            start_index = self.current_page * CAMS_PER_PAGE
            for i, canvas in enumerate(self.camera_canvases):
                global_index = start_index + i
                if global_index < self.num_total_cameras:
                    frame = self.latest_frames.get(global_index)
                    if frame is not None:
                        frame_resized = cv2.resize(frame, (CANVAS_WIDTH, CANVAS_HEIGHT))
                        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                        photo = ImageTk.PhotoImage(image=Image.fromarray(frame_rgb))
                        canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                        canvas.image = photo
                    else:
                        canvas.delete("all")
                        canvas.create_text(CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2, text="Sin Señal", fill="white", font=("Helvetica", 16))
        if self.running: self.window.after(self.delay, self.update_gui_frames)
    def stop_all_active_streams(self):
        for _, (thread, _, flag) in list(self.active_streams.items()):
            flag[0] = False
            thread.join(timeout=1.0)
        self.active_streams.clear(); self.latest_frames.clear()
    def next_page(self):
        if self.current_page < self.total_pages - 1: self.current_page += 1; self.update_page_view()
    def prev_page(self):
        if self.current_page > 0: self.current_page -= 1; self.update_page_view()

# --- Re-incluyo la clase SettingsDialog por completitud ---
class SettingsDialog(tk.Toplevel):
    def __init__(self, master, current_urls):
        super().__init__(master)
        self.transient(master); self.title("Administrar Cámaras"); self.geometry("600x400"); self.result = None
        main_frame = ttk.Frame(self, padding="10"); main_frame.pack(fill="both", expand=True)
        list_frame = ttk.LabelFrame(main_frame, text="Lista de Cámaras"); list_frame.pack(fill="both", expand=True, pady=5)
        self.listbox = tk.Listbox(list_frame); self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview); scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        for url in current_urls: self.listbox.insert(tk.END, url)
        button_frame = ttk.Frame(main_frame); button_frame.pack(fill="x", pady=5)
        ttk.Button(button_frame, text="Añadir", command=self.add_url).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Editar", command=self.edit_url).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Eliminar", command=self.remove_url).pack(side="left", padx=5)
        action_frame = ttk.Frame(main_frame); action_frame.pack(side="bottom", fill="x", pady=(10,0))
        ttk.Button(action_frame, text="Guardar y Cerrar", command=self.save_and_close).pack(side="right")
        ttk.Button(action_frame, text="Cancelar", command=self.cancel).pack(side="right", padx=10)
        self.protocol("WM_DELETE_WINDOW", self.cancel); self.grab_set(); self.wait_window(self)
    def add_url(self):
        new_url = simpledialog.askstring("Añadir Cámara", "Introduce la URL RTSP:", parent=self)
        if new_url: self.listbox.insert(tk.END, new_url)
    def edit_url(self):
        if not self.listbox.curselection(): return
        idx = self.listbox.curselection()[0]
        new_url = simpledialog.askstring("Editar Cámara", "Edita la URL:", initialvalue=self.listbox.get(idx), parent=self)
        if new_url: self.listbox.delete(idx); self.listbox.insert(idx, new_url)
    def remove_url(self):
        if self.listbox.curselection() and messagebox.askyesno("Confirmar", "¿Eliminar?", parent=self): self.listbox.delete(self.listbox.curselection()[0])
    def save_and_close(self): self.result = list(self.listbox.get(0, tk.END)); self.destroy()
    def cancel(self): self.result = None; self.destroy()

# --- Punto de Entrada del Programa ---
if __name__ == '__main__':
    root = tk.Tk()
    sv_ttk.set_theme("dark")
    root.geometry("1280x720")
    app = CameraViewerApp(root, "Visor de Cámaras con Detección")