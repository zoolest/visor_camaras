# --- VISOR MULTI-CÁMARA CON OPENCV (VERSIÓN FINAL ESTABLE SIN AUDIO) ---
# --- VERSIÓN CON CORRECCIÓN DE ASPECTO Y OPTIMIZACIÓN DE RENDIMIENTO ---

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import cv2
import threading
from PIL import Image, ImageTk
import os
import math
import time
from urllib.parse import urlparse
import sv_ttk

# --- FORZAR TCP PARA UNA CONEXIÓN RTSP RÁPIDA ---
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# --- CONFIGURACIÓN GLOBAL ---
CONFIG_FILE = "cameras.txt"
CAMS_PER_PAGE = 6
GRID_COLS = 3
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
        
        self.active_streams = {}
        self.latest_frames = {}
        self.overlay_buttons = {}
        self.last_frame_time = {}
        self.num_total_cameras = len(self.all_camera_urls)
        
        self.current_page = 0
        self.total_pages = 0
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None
        self.true_fullscreen = False
        self.hide_controls_job = None
        self.running = True

        # --- UI ---
        self.top_bar = ttk.Frame(self.window)
        self.top_bar.pack(side="top", fill="x", padx=10, pady=5)
        ttk.Button(self.top_bar, text="Administrar Cámaras", command=self.open_settings).pack(side="left")

        self.fullscreen_controls_top = ttk.Frame(self.top_bar)
        ttk.Button(self.fullscreen_controls_top, text="Volver a la Cuadrícula", command=self.exit_fullscreen).pack(side="right", padx=(5,0))
        ttk.Button(self.fullscreen_controls_top, text="Pantalla Completa", command=self.enter_true_fullscreen).pack(side="right", padx=(5,0))
        ttk.Button(self.fullscreen_controls_top, text="🔄 Recargar", width=10, command=self._reload_fullscreen_stream).pack(side="right", padx=(5,0))
        
        self.grid_frame = ttk.Frame(self.window); self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.camera_canvases = []
        
        self.bottom_bar = ttk.Frame(self.window); self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)
        self.prev_button = ttk.Button(self.bottom_bar, text="<< Anterior", command=self.prev_page); self.prev_button.pack(side="left")
        self.page_label = ttk.Label(self.bottom_bar, text="Página 0 de 0", anchor="center"); self.page_label.pack(side="left", fill="x", expand=True)
        self.next_button = ttk.Button(self.bottom_bar, text="Siguiente >>", command=self.next_page); self.next_button.pack(side="right")
        
        self.fullscreen_frame = ttk.Frame(self.window)
        self.fullscreen_label = ttk.Label(self.fullscreen_frame, text="", font=("Helvetica", 14, "bold")); self.fullscreen_label.pack(pady=(5,0))
        self.fullscreen_canvas = tk.Canvas(self.fullscreen_frame, bg="black")
        self.fullscreen_canvas.pack(fill="both", expand=True)
        
        self.fs_exit_hover_button = ttk.Button(self.fullscreen_canvas, text="Salir de Pantalla Completa (Esc)", command=self.exit_true_fullscreen)

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_page_view()
        # --- CAMBIO: Reducir tasa de refresco para bajar uso de CPU ---
        self.delay = 100 # ms, 10 FPS
        self.update_gui_frames()
        self.check_streams_health()
        self.window.mainloop()

    def check_streams_health(self):
        if not self.running or self.fullscreen_mode:
            self.window.after(10000, self.check_streams_health)
            return

        for index in list(self.active_streams.keys()):
            last_time = self.last_frame_time.get(index, 0)
            if time.time() - last_time > 15:
                print(f"Stream de cámara {index} parece congelado. Reiniciando...")
                self.reload_grid_stream(index)
        
        self.window.after(10000, self.check_streams_health)

    def update_page_view(self):
        self.stop_all_active_streams()
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        
        self.camera_canvases = []
        self.overlay_buttons.clear()

        self.num_total_cameras = len(self.all_camera_urls)
        self.total_pages = math.ceil(self.num_total_cameras / CAMS_PER_PAGE) if self.num_total_cameras > 0 else 1
        self.current_page = max(0, min(self.current_page, self.total_pages - 1))

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
            
            pane = ttk.LabelFrame(self.grid_frame, text="Vacío")
            pane.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            canvas = tk.Canvas(pane, bg="black")
            canvas.pack(fill="both", expand=True)
            self.camera_canvases.append(canvas)

            if global_index < self.num_total_cameras:
                url = self.all_camera_urls[global_index]
                pane.config(text=self._extract_name_from_url(url, default_name=f"Cámara {global_index+1}"))
                
                button_overlay_frame = ttk.Frame(pane)
                self.overlay_buttons[global_index] = button_overlay_frame
                
                expand_button = ttk.Button(button_overlay_frame, text="⛶", width=3, command=lambda idx=global_index: self.enter_fullscreen(idx))
                expand_button.pack(side="left", padx=(5,0))
                
                reload_button = ttk.Button(button_overlay_frame, text="🔄", width=3, command=lambda idx=global_index: self.reload_grid_stream(idx))
                reload_button.pack(side="left", padx=(5,0))

                pane.bind("<Enter>", lambda e, idx=global_index: self.show_overlay_buttons(idx))
                pane.bind("<Leave>", lambda e, idx=global_index: self.hide_overlay_buttons(idx))
                
                self.start_stream(global_index, url)

    def show_overlay_buttons(self, global_index):
        if global_index in self.overlay_buttons:
            self.overlay_buttons[global_index].place(relx=1.0, y=5, x=-5, anchor="ne")

    def hide_overlay_buttons(self, global_index):
        if global_index in self.overlay_buttons:
            self.overlay_buttons[global_index].place_forget()

    def start_stream(self, global_index, url):
        if url and global_index not in self.active_streams:
            self.latest_frames[global_index] = ("connecting", None)
            threading.Thread(target=self._stream_worker, args=(global_index, url), daemon=True).start()

    def _stream_worker(self, global_index, url):
        stream_url = url.replace("stream1", "stream2")
        cap = cv2.VideoCapture(stream_url)
        
        if not cap.isOpened():
            self.latest_frames[global_index] = ("error", "Error de Conexión")
            return

        flag = [True]
        thread = threading.Thread(target=self.read_frames, args=(cap, global_index, flag), daemon=True)
        self.active_streams[global_index] = (thread, cap, flag)
        self.last_frame_time[global_index] = time.time()
        thread.start()

    def read_frames(self, cap, global_index, running_flag):
        while running_flag[0]:
            ret, frame = cap.read()
            if ret:
                self.latest_frames[global_index] = ("playing", frame)
                self.last_frame_time[global_index] = time.time()
            else:
                self.latest_frames[global_index] = ("no_signal", None)
                time.sleep(1)
        cap.release()

    def reload_grid_stream(self, global_index):
        if global_index in self.active_streams:
            thread, _, flag = self.active_streams[global_index]
            flag[0] = False
            thread.join(timeout=1.0)
            del self.active_streams[global_index]
        
        self.last_frame_time.pop(global_index, None)
        url = self.all_camera_urls[global_index]
        self.start_stream(global_index, url)

    def update_gui_frames(self):
        # Unificar la lógica de dibujado en una función auxiliar
        def draw_frame(canvas, frame_data):
            canvas.delete("all")
            canvas_w = canvas.winfo_width()
            canvas_h = canvas.winfo_height()

            if canvas_w <= 1 or canvas_h <= 1: return # No dibujar si el canvas no es visible

            if frame_data:
                status, data = frame_data
                if status == "playing":
                    h, w, _ = data.shape
                    # --- CAMBIO: Lógica de letterboxing para TODAS las vistas ---
                    scale = min(canvas_w / w, canvas_h / h)
                    new_w, new_h = int(w * scale), int(h * scale)
                    
                    frame_resized = cv2.resize(data, (new_w, new_h))
                    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    
                    img_pil = Image.fromarray(frame_rgb)
                    bg_image = Image.new('RGB', (canvas_w, canvas_h), 'black')
                    offset = ((canvas_w - new_w) // 2, (canvas_h - new_h) // 2)
                    bg_image.paste(img_pil, offset)
                    
                    photo = ImageTk.PhotoImage(image=bg_image)
                    canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                    canvas.image = photo
                elif status == "error":
                    canvas.create_text(canvas_w / 2, canvas_h / 2, text=data, fill="#E57373", font=("Helvetica", 16))
                else: # 'connecting', 'no_signal'
                    canvas.create_text(canvas_w / 2, canvas_h / 2, text=status.replace("_", " ").title(), fill="white", font=("Helvetica", 16))
            else: # Si no hay state_info (poco probable pero seguro)
                canvas.create_text(canvas_w / 2, canvas_h / 2, text="Iniciando...", fill="white", font=("Helvetica", 16))

        if self.fullscreen_mode:
            state_info = self.latest_frames.get(self.fullscreen_camera_index)
            draw_frame(self.fullscreen_canvas, state_info)
        else:
            for i, canvas in enumerate(self.camera_canvases):
                global_index = self.current_page * CAMS_PER_PAGE + i
                if global_index < self.num_total_cameras:
                    state_info = self.latest_frames.get(global_index)
                    draw_frame(canvas, state_info)

        if self.running:
            self.window.after(self.delay, self.update_gui_frames)

    def _reload_fullscreen_stream(self):
        if self.fullscreen_camera_index is not None:
            self.reload_grid_stream(self.fullscreen_camera_index)

    def enter_fullscreen(self, global_index):
        self.fullscreen_mode = True
        self.fullscreen_camera_index = global_index
        self._update_fullscreen_info()
        
        self.grid_frame.pack_forget()
        self.bottom_bar.pack_forget()
        self.fullscreen_frame.pack(fill="both", expand=True)
        self.fullscreen_controls_top.pack(side="right", padx=5)
        
        self.window.bind("<Escape>", self.handle_escape)
        self.window.bind("<Right>", self.next_camera_fullscreen)
        self.window.bind("<Left>", self.prev_camera_fullscreen)

    def exit_fullscreen(self, event=None):
        if self.true_fullscreen: self.exit_true_fullscreen()
        
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None
        
        self.fullscreen_frame.pack_forget()
        self.fullscreen_controls_top.pack_forget()
        
        self.window.unbind("<Escape>")
        self.window.unbind("<Right>")
        self.window.unbind("<Left>")
        
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)
        
    def _show_fs_exit_button(self, event=None):
        self.fs_exit_hover_button.place(relx=0.5, rely=1.0, x=0, y=-10, anchor="s")
        if self.hide_controls_job:
            self.window.after_cancel(self.hide_controls_job)
        self.hide_controls_job = self.window.after(3000, self._hide_fs_exit_button)

    def _hide_fs_exit_button(self):
        self.fs_exit_hover_button.place_forget()

    def enter_true_fullscreen(self, event=None):
        self.true_fullscreen = True
        self.top_bar.pack_forget()
        self.window.attributes('-fullscreen', True)
        self.window.bind("<Motion>", self._show_fs_exit_button)

    def exit_true_fullscreen(self, event=None):
        self.true_fullscreen = False
        self.window.attributes('-fullscreen', False)
        self.window.unbind("<Motion>")
        if self.hide_controls_job:
            self.window.after_cancel(self.hide_controls_job)
            self.hide_controls_job = None
        self._hide_fs_exit_button()
        self.top_bar.pack(side="top", fill="x", padx=10, pady=5)
        
    def handle_escape(self, event=None):
        if self.true_fullscreen:
            self.exit_true_fullscreen()
        else:
            self.exit_fullscreen()
            
    def _update_fullscreen_info(self):
        if self.fullscreen_camera_index is not None:
            camera_name = self._extract_name_from_url(self.all_camera_urls[self.fullscreen_camera_index], default_name=f"CÁMARA {self.fullscreen_camera_index+1}")
            self.fullscreen_label.config(text=f"{camera_name}")

    def next_camera_fullscreen(self, event=None):
        if self.num_total_cameras <= 1: return
        self.fullscreen_camera_index = (self.fullscreen_camera_index + 1) % self.num_total_cameras
        self._update_fullscreen_info()

    def prev_camera_fullscreen(self, event=None):
        if self.num_total_cameras <= 1: return
        self.fullscreen_camera_index = (self.fullscreen_camera_index - 1 + self.num_total_cameras) % self.num_total_cameras
        self._update_fullscreen_info()

    def on_closing(self):
        self.running = False
        self.stop_all_active_streams()
        self.window.after(100, self.window.destroy)

    def stop_all_active_streams(self):
        for _, (thread, _, flag) in list(self.active_streams.items()):
            flag[0] = False
            thread.join(timeout=1.0)
        self.active_streams.clear()
        self.latest_frames.clear()
        self.last_frame_time.clear()
    
    def load_urls_from_file(self):
        if not os.path.exists(CONFIG_FILE): return []
        with open(CONFIG_FILE, "r") as f: return [line.strip() for line in f if line.strip()]
    def save_urls_to_file(self):
        with open(CONFIG_FILE, "w") as f:
            for url in self.all_camera_urls: f.write(url + "\n")
    def _extract_name_from_url(self, url, default_name="Cámara sin nombre"):
        try:
            parsed_url = urlparse(url)
            return parsed_url.username or parsed_url.hostname or default_name
        except Exception:
            return default_name
    def open_settings(self):
        if self.fullscreen_mode: self.exit_fullscreen()
        dialog = SettingsDialog(self.window, self.all_camera_urls)
        if dialog.result is not None:
            self.all_camera_urls = dialog.result
            self.save_urls_to_file()
            self.current_page = 0
            self.update_page_view()
    def next_page(self):
        if self.current_page < self.total_pages - 1: self.current_page += 1; self.update_page_view()
    def prev_page(self):
        if self.current_page > 0: self.current_page -= 1; self.update_page_view()

# --- Punto de Entrada del Programa ---
if __name__ == '__main__':
    root = tk.Tk()
    sv_ttk.set_theme("dark")
    root.geometry("1280x720")
    if os.name == 'nt':
        root.wm_attributes("-transparentcolor", "white")
        
    app = CameraViewerApp(root, "Visor de Cámaras Avanzado (OpenCV)")