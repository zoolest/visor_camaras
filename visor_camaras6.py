# --- VISOR MULTI-CÁMARA USANDO OpenCV (SIN AUDIO) ---
# --- VERSIÓN CON MODO DE PANTALLA COMPLETA REAL ---

import cv2
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from PIL import Image, ImageTk
import os
import math
import time
from urllib.parse import urlparse

# --- CONFIGURACIÓN GLOBAL ---
CONFIG_FILE = "cameras.txt"
CAMS_PER_PAGE = 6
GRID_COLS = 3
CANVAS_WIDTH = 480
CANVAS_HEIGHT = 270
# --------------------

# --- CLASE PARA LA VENTANA DE AJUSTES ---
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

# --- CLASE PRINCIPAL DE LA APLICACIÓN ---
class CameraViewerApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        
        self.all_camera_urls = self.load_urls_from_file()
        
        self.active_streams = {}; self.latest_frames = {}
        self.current_page = 0; self.total_pages = 0
        self.fullscreen_mode = False; self.fullscreen_camera_index = None
        self.true_fullscreen = False # Nuevo estado para la pantalla completa real

        top_bar = ttk.Frame(self.window); top_bar.pack(side="top", fill="x", padx=10, pady=5)
        ttk.Button(top_bar, text="Administrar Cámaras", command=self.open_settings).pack(side="left")

        self.grid_frame = ttk.Frame(self.window); self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.camera_canvases = []

        self.bottom_bar = ttk.Frame(self.window); self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)
        self.prev_button = ttk.Button(self.bottom_bar, text="<< Anterior", command=self.prev_page); self.prev_button.pack(side="left")
        self.page_label = ttk.Label(self.bottom_bar, text="Página 0 de 0", anchor="center"); self.page_label.pack(side="left", fill="x", expand=True)
        self.next_button = ttk.Button(self.bottom_bar, text="Siguiente >>", command=self.next_page); self.next_button.pack(side="right")
        
        # --- Configuración de la vista de cámara única ---
        self.fullscreen_frame = ttk.Frame(self.window)
        self.fullscreen_label = ttk.Label(self.fullscreen_frame, text="", font=("Helvetica", 14, "bold")); self.fullscreen_label.pack(pady=(10,5))
        self.fullscreen_canvas = tk.Canvas(self.fullscreen_frame, bg="black", cursor="hand2")
        self.fullscreen_canvas.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Frame para los botones de la vista completa
        fullscreen_button_frame = ttk.Frame(self.fullscreen_frame)
        fullscreen_button_frame.pack(pady=10)

        self.back_to_grid_button = ttk.Button(fullscreen_button_frame, text="Volver a la Cuadrícula", command=self.exit_fullscreen)
        self.back_to_grid_button.pack(side="left", padx=5)

        self.enter_true_fullscreen_button = ttk.Button(fullscreen_button_frame, text="Pantalla Completa", command=self.enter_true_fullscreen)
        self.enter_true_fullscreen_button.pack(side="left", padx=5)

        self.exit_true_fullscreen_button = ttk.Button(fullscreen_button_frame, text="Salir de Pantalla Completa", command=self.exit_true_fullscreen)
        # Este botón se mostrará/ocultará, así que no lo empaquetamos ahora
        
        self.running = True
        self.update_page_view()
        self.delay = 33
        self.update_gui_frames()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.mainloop()

    # --- Métodos para la pantalla completa real ---
    def enter_true_fullscreen(self):
        self.true_fullscreen = True
        self.window.attributes('-fullscreen', True)
        self.back_to_grid_button.pack_forget()
        self.enter_true_fullscreen_button.pack_forget()
        self.exit_true_fullscreen_button.pack(side="left", padx=5)

    def exit_true_fullscreen(self):
        self.true_fullscreen = False
        self.window.attributes('-fullscreen', False)
        self.exit_true_fullscreen_button.pack_forget()
        self.back_to_grid_button.pack(side="left", padx=5)
        self.enter_true_fullscreen_button.pack(side="left", padx=5)

    def handle_escape(self, event=None):
        """Maneja la tecla Esc de forma inteligente."""
        if self.true_fullscreen:
            self.exit_true_fullscreen()
        else:
            self.exit_fullscreen()
            
    # --- Métodos de la aplicación principal (con modificaciones) ---
    def enter_fullscreen(self, global_index):
        self.fullscreen_mode = True
        self.fullscreen_camera_index = global_index
        camera_name = self._extract_name_from_url(self.all_camera_urls[global_index], default_name=f"CÁMARA {global_index+1}")
        self.fullscreen_label.config(text=f"{camera_name} - VISTA COMPLETA")
        self.grid_frame.pack_forget()
        self.bottom_bar.pack_forget()
        self.fullscreen_frame.pack(fill="both", expand=True)
        
        self.fullscreen_canvas.bind("<Double-1>", lambda e: self.exit_fullscreen())
        self.window.bind("<Escape>", self.handle_escape)

    def exit_fullscreen(self, event=None):
        # Si estamos en pantalla completa real, salir de ella primero
        if self.true_fullscreen:
            self.exit_true_fullscreen()
            
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None
        self.fullscreen_frame.pack_forget()
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)

        self.fullscreen_canvas.unbind("<Double-1>")
        self.window.unbind("<Escape>")

    # --- Resto de los métodos (sin cambios) ---
    
    def _extract_name_from_url(self, url, default_name="Cámara sin nombre"):
        try:
            parsed_url = urlparse(url)
            return parsed_url.username or parsed_url.hostname or default_name
        except Exception:
            return default_name

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
                canvas.bind("<Button-3>", lambda event, idx=global_index: self.show_context_menu(event, idx))
                self.start_stream(global_index, url)
            else:
                canvas.config(bg="gray80")

    def start_stream(self, global_index, url):
        if url and global_index not in self.active_streams:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                thread_running_flag = [True]
                thread = threading.Thread(target=self.read_frames, args=(cap, global_index, thread_running_flag), daemon=True)
                self.active_streams[global_index] = (thread, cap, thread_running_flag)
                thread.start()

    def read_frames(self, cap, global_index, running_flag):
        while running_flag[0]:
            ret, frame = cap.read()
            if ret:
                self.latest_frames[global_index] = frame
            else:
                self.latest_frames[global_index] = None
                time.sleep(1)
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
        
        if self.running:
            self.window.after(self.delay, self.update_gui_frames)

    def reload_stream(self, global_index):
        print(f"Recargando stream para la cámara {global_index}...")
        if global_index in self.active_streams:
            thread, cap, flag = self.active_streams[global_index]
            flag[0] = False
            thread.join(timeout=1.0)
            del self.active_streams[global_index]
        if global_index in self.latest_frames:
            self.latest_frames[global_index] = None

        url = self.all_camera_urls[global_index]
        self.start_stream(global_index, url)
        
    def show_context_menu(self, event, global_index):
        context_menu = tk.Menu(self.window, tearoff=0)
        context_menu.add_command(label="Recargar Stream", command=lambda: self.reload_stream(global_index))
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def stop_all_active_streams(self):
        for global_index, (thread, cap, flag) in list(self.active_streams.items()):
            flag[0] = False
            thread.join(timeout=1.0)
        self.active_streams.clear()
        self.latest_frames.clear()

    def on_closing(self):
        self.running = False
        self.stop_all_active_streams()
        self.window.after(100, self.window.destroy)

    def next_page(self):
        if self.current_page < self.total_pages - 1: self.current_page += 1; self.update_page_view()
    def prev_page(self):
        if self.current_page > 0: self.current_page -= 1; self.update_page_view()

# --- Punto de Entrada del Programa ---
if __name__ == '__main__':
    root = tk.Tk()
    root.geometry("1280x720")
    app = CameraViewerApp(root, "Visor de Cámaras Avanzado (OpenCV)")