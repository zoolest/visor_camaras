import cv2
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from PIL import Image, ImageTk
import os
import math
import time

# --- CONFIGURACIÓN GLOBAL ---
CONFIG_FILE = "cameras.txt"
CAMS_PER_PAGE = 6
GRID_COLS = 2 # Columnas fijas para un diseño de 3x2 por página
CANVAS_WIDTH = 480
CANVAS_HEIGHT = 270
# --------------------

# --- CLASE PARA LA VENTANA DE AJUSTES ---
class SettingsDialog(tk.Toplevel):
    """
    Una ventana de diálogo independiente para que el usuario pueda
    añadir, editar y eliminar las URLs de las cámaras.
    """
    def __init__(self, master, current_urls):
        super().__init__(master)
        self.transient(master) # Se mantiene sobre la ventana principal
        self.title("Administrar Cámaras")
        self.geometry("600x400")
        self.result = None # Aquí se guardará la lista de URLs si el usuario guarda

        # Creación de Widgets (la interfaz de esta ventana)
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        list_frame = ttk.LabelFrame(main_frame, text="Lista de Cámaras")
        list_frame.pack(fill="both", expand=True, pady=5)
        
        self.listbox = tk.Listbox(list_frame)
        self.listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        for url in current_urls: self.listbox.insert(tk.END, url)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=5)
        ttk.Button(button_frame, text="Añadir", command=self.add_url).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Editar", command=self.edit_url).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Eliminar", command=self.remove_url).pack(side="left", padx=5)
        
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(side="bottom", fill="x", pady=(10,0))
        ttk.Button(action_frame, text="Guardar y Cerrar", command=self.save_and_close).pack(side="right")
        ttk.Button(action_frame, text="Cancelar", command=self.cancel).pack(side="right", padx=10)
        
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.grab_set() # Hace que la ventana sea modal
        self.wait_window(self)

    def add_url(self):
        new_url = simpledialog.askstring("Añadir Cámara", "Introduce la URL RTSP:", parent=self)
        if new_url: self.listbox.insert(tk.END, new_url)

    def edit_url(self):
        if not self.listbox.curselection(): return
        idx = self.listbox.curselection()[0]
        new_url = simpledialog.askstring("Editar Cámara", "Edita la URL:", initialvalue=self.listbox.get(idx), parent=self)
        if new_url: self.listbox.delete(idx); self.listbox.insert(idx, new_url)

    def remove_url(self):
        if self.listbox.curselection() and messagebox.askyesno("Confirmar", "¿Eliminar cámara seleccionada?", parent=self):
            self.listbox.delete(self.listbox.curselection()[0])

    def save_and_close(self):
        self.result = list(self.listbox.get(0, tk.END))
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

# --- CLASE PRINCIPAL DE LA APLICACIÓN ---
class CameraViewerApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        
        self.all_camera_urls = self.load_urls_from_file()
        
        self.active_streams = {}
        self.latest_frames = {}
        self.current_page = 0
        self.total_pages = 0
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None

        # --- Creación de la Interfaz Principal ---
        top_bar = ttk.Frame(self.window)
        top_bar.pack(side="top", fill="x", padx=10, pady=5)
        ttk.Button(top_bar, text="Administrar Cámaras", command=self.open_settings).pack(side="left")

        self.grid_frame = ttk.Frame(self.window)
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.camera_canvases = []

        self.bottom_bar = ttk.Frame(self.window)
        self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)
        self.prev_button = ttk.Button(self.bottom_bar, text="<< Anterior", command=self.prev_page)
        self.prev_button.pack(side="left")
        self.page_label = ttk.Label(self.bottom_bar, text="Página 0 de 0", anchor="center")
        self.page_label.pack(side="left", fill="x", expand=True)
        self.next_button = ttk.Button(self.bottom_bar, text="Siguiente >>", command=self.next_page)
        self.next_button.pack(side="right")
        
        self.fullscreen_frame = ttk.Frame(self.window)
        self.fullscreen_label = ttk.Label(self.fullscreen_frame, text="", font=("Helvetica", 14, "bold"))
        self.fullscreen_label.pack(pady=(10,5))
        self.fullscreen_canvas = tk.Canvas(self.fullscreen_frame, bg="black")
        self.fullscreen_canvas.pack(fill="both", expand=True, padx=10, pady=5)
        ttk.Button(self.fullscreen_frame, text="Volver a la Cuadrícula", command=self.exit_fullscreen).pack(pady=10)
        
        self.running = True
        self.update_page_view()
        self.delay = 33
        self.update_gui_frames()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.mainloop()

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
            self.all_camera_urls = dialog.result
            self.save_urls_to_file()
            self.current_page = 0
            self.update_page_view()

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

        start_index = self.current_page * CAMS_PER_PAGE
        end_index = min(start_index + CAMS_PER_PAGE, self.num_total_cameras)
        
        for i in range(start_index, end_index):
            local_index = i - start_index
            row, col = local_index // GRID_COLS, local_index % GRID_COLS

            pane = ttk.LabelFrame(self.grid_frame, text=f"CÁMARA {i + 1}")
            pane.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            canvas = tk.Canvas(pane, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="black", cursor="hand2")
            canvas.pack(fill="both", expand=True)
            
            canvas.bind("<Double-1>", lambda event, idx=i: self.enter_fullscreen(idx))
            
            self.camera_canvases.append(canvas)
            self.start_stream(i, self.all_camera_urls[i])

    def enter_fullscreen(self, global_index):
        self.fullscreen_mode = True
        self.fullscreen_camera_index = global_index
        
        self.grid_frame.pack_forget()
        self.bottom_bar.pack_forget()
        
        self.fullscreen_label.config(text=f"CÁMARA {global_index + 1} - VISTA COMPLETA")
        self.fullscreen_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def exit_fullscreen(self):
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None
        
        self.fullscreen_frame.pack_forget()
        
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)

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
                    
                    bg_image = Image.new('RGB', (canvas_w, canvas_h), 'black')
                    offset = ((canvas_w - new_w) // 2, (canvas_h - new_h) // 2)
                    bg_image.paste(Image.fromarray(frame_rgb), offset)
                    photo = ImageTk.PhotoImage(image=bg_image)
                    
                    canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                    canvas.image = photo
            else:
                canvas.delete("all")
                canvas.create_text(canvas.winfo_width()//2, canvas.winfo_height()//2, text="Sin Señal", fill="white", font=("Helvetica", 24))
        else:
            start_index = self.current_page * CAMS_PER_PAGE
            for i, canvas in enumerate(self.camera_canvases):
                global_index = start_index + i
                frame = self.latest_frames.get(global_index)
                if frame is not None:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_resized = cv2.resize(frame_rgb, (CANVAS_WIDTH, CANVAS_HEIGHT))
                    photo = ImageTk.PhotoImage(image=Image.fromarray(frame_resized))
                    canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                    canvas.image = photo
                else:
                    canvas.delete("all")
                    canvas.create_text(CANVAS_WIDTH//2, CANVAS_HEIGHT//2, text="Sin Señal", fill="white", font=("Helvetica", 16))
        
        if self.running:
            self.window.after(self.delay, self.update_gui_frames)

    def next_page(self):
        if self.current_page < self.total_pages - 1: self.current_page += 1; self.update_page_view()

    def prev_page(self):
        if self.current_page > 0: self.current_page -= 1; self.update_page_view()

    def start_stream(self, global_index, url):
        if not url or global_index in self.active_streams: return
        running_flag = [True]; cap = cv2.VideoCapture(url)
        if not cap.isOpened(): return
        
        def read_frames():
            while running_flag[0] and cap.isOpened():
                ret, frame = cap.read()
                self.latest_frames[global_index] = frame if ret else None
                if not ret: time.sleep(1)
            cap.release()
        
        thread = threading.Thread(target=read_frames, daemon=True)
        thread.start()
        self.active_streams[global_index] = (thread, cap, running_flag)

    def stop_all_active_streams(self):
        for global_index, (thread, cap, flag) in list(self.active_streams.items()):
            flag[0] = False
            thread.join(timeout=1.0)
        self.active_streams.clear()
        self.latest_frames.clear()

    def on_closing(self):
        self.running = False
        self.stop_all_active_streams()
        self.window.destroy()

# --- Punto de Entrada del Programa ---
if __name__ == '__main__':
    root = tk.Tk()
    app = CameraViewerApp(root, "Visor de Cámaras Avanzado")