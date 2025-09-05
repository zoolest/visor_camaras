# --- VISOR MULTI-CÁMARA CON AUDIO SELECTIVO (VLC) ---
# --- VERSIÓN FINAL SIN DEPENDENCIAS DE ICONOS ---

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import vlc
import os
import math
from urllib.parse import urlparse
import sv_ttk

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
        
        self.active_players = {}
        self.audio_buttons = {}
        
        self.audio_source_index = None

        self.current_page = 0
        self.total_pages = 0
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None

        # Instancia de VLC (Compatible con Windows/Linux)
        self.vlc_instance = vlc.Instance("--quiet")
        
        # --- UI (Interfaz de Usuario) ---
        top_bar = ttk.Frame(self.window); top_bar.pack(side="top", fill="x", padx=10, pady=5)
        ttk.Button(top_bar, text="Administrar Cámaras", command=self.open_settings).pack(side="left")

        self.grid_frame = ttk.Frame(self.window); self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.bottom_bar = ttk.Frame(self.window); self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)
        self.prev_button = ttk.Button(self.bottom_bar, text="<< Anterior", command=self.prev_page); self.prev_button.pack(side="left")
        self.page_label = ttk.Label(self.bottom_bar, text="Página 0 de 0", anchor="center"); self.page_label.pack(side="left", fill="x", expand=True)
        self.next_button = ttk.Button(self.bottom_bar, text="Siguiente >>", command=self.next_page); self.next_button.pack(side="right")
        
        self.fullscreen_frame = tk.Frame(self.window, bg="black")
        self.fullscreen_video_frame = tk.Frame(self.fullscreen_frame, bg="black")
        self.fullscreen_video_frame.pack(fill="both", expand=True)
        ttk.Button(self.fullscreen_frame, text="Volver a la Cuadrícula", command=self.exit_fullscreen).pack(pady=10)
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_page_view()
        self.window.mainloop()

    def update_page_view(self):
        self.stop_all_streams()
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        
        self.audio_buttons.clear()

        num_total_cameras = len(self.all_camera_urls)
        self.total_pages = math.ceil(num_total_cameras / CAMS_PER_PAGE) if num_total_cameras > 0 else 1
        
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
            pane.grid_rowconfigure(0, weight=1)
            pane.grid_columnconfigure(0, weight=1)

            if global_index < num_total_cameras:
                url = self.all_camera_urls[global_index]
                pane.config(text=self._extract_name_from_url(url, default_name=f"Cámara {global_index+1}"))
                
                video_frame = tk.Frame(pane, bg="black")
                video_frame.grid(row=0, column=0, sticky="nsew")
                
                # CAMBIO: Botón de audio con texto/emoji en lugar de icono
                audio_button = ttk.Button(pane, text="🔇", width=3, command=lambda idx=global_index: self.toggle_audio_for_camera(idx))
                audio_button.place(x=5, y=5, anchor="nw")
                self.audio_buttons[global_index] = audio_button
                
                video_frame.bind("<Double-1>", lambda e, idx=global_index: self.enter_fullscreen(idx))

                self.start_stream(global_index, url, video_frame)
    
    def start_stream(self, global_index, url, frame_widget):
        if global_index in self.active_players: return

        player = self.vlc_instance.media_player_new()
        media = self.vlc_instance.media_new(url)
        media.add_option(':rtsp-tcp')
        player.set_media(media)
        
        player.set_hwnd(frame_widget.winfo_id())
        
        player.audio_set_mute(True)
        
        player.play()
        self.active_players[global_index] = player

    def toggle_audio_for_camera(self, global_index):
        # Si hay una cámara sonando actualmente, la muteamos primero
        if self.audio_source_index is not None and self.audio_source_index in self.active_players:
            current_player = self.active_players[self.audio_source_index]
            current_player.audio_set_mute(True)
            if self.audio_source_index in self.audio_buttons:
                # CAMBIO: Actualizar el texto del botón a "muteado"
                self.audio_buttons[self.audio_source_index].config(text="🔇")

        # Si el usuario hizo clic en la misma cámara que ya sonaba, la dejamos muteada.
        if self.audio_source_index == global_index:
            self.audio_source_index = None
            return

        # Activamos el audio de la nueva cámara seleccionada
        if global_index in self.active_players:
            new_player = self.active_players[global_index]
            new_player.audio_set_mute(False)
            self.audio_source_index = global_index
            if global_index in self.audio_buttons:
                # CAMBIO: Actualizar el texto del botón a "sonando"
                self.audio_buttons[global_index].config(text="🔊")
    
    def enter_fullscreen(self, global_index):
        if not global_index in self.active_players: return
        self.fullscreen_mode = True
        self.fullscreen_camera_index = global_index
        
        self.grid_frame.pack_forget()
        self.bottom_bar.pack_forget()
        self.fullscreen_frame.pack(fill="both", expand=True)
        
        player = self.active_players[global_index]
        player.set_hwnd(self.fullscreen_video_frame.winfo_id())

    def exit_fullscreen(self, event=None):
        if self.fullscreen_camera_index is None: return

        # Lógica para encontrar el frame original y devolver el video
        children = self.grid_frame.winfo_children()
        on_page_index = self.fullscreen_camera_index % CAMS_PER_PAGE
        
        if on_page_index < len(children):
            original_container = children[on_page_index]
            original_video_frame = original_container.winfo_children()[0]
            player = self.active_players[self.fullscreen_camera_index]
            player.set_hwnd(original_video_frame.winfo_id())
        
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None
        
        self.fullscreen_frame.pack_forget()
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)
        
    def on_closing(self):
        self.stop_all_streams()
        self.window.destroy()

    def stop_all_streams(self):
        for player in self.active_players.values(): player.stop()
        self.active_players.clear()
        self.audio_source_index = None
    
    def load_urls_from_file(self):
        if not os.path.exists(CONFIG_FILE): return []
        with open(CONFIG_FILE, "r") as f: return [line.strip() for line in f if line.strip()]
    
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
    app = CameraViewerApp(root, "Visor de Cámaras con Audio Selectivo")