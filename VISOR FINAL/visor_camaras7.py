# --- VISOR MULTI-CÁMARA CON AUDIO Y NAVEGACIÓN COMPLETA (VLC) ---
# --- VERSIÓN CON CONTROLES EN LA PARTE SUPERIOR ---

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
CAM_FRAME_WIDTH = 480
CAM_FRAME_HEIGHT = 270
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
        self.camera_video_frames = {}
        self.overlay_buttons = {}
        self.num_total_cameras = len(self.all_camera_urls)
        
        self.audio_source_index = None
        self.current_page = 0
        self.total_pages = 0
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None
        self.true_fullscreen = False
        self.fullscreen_player = None
        self.hide_controls_job = None

        self.vlc_instance = vlc.Instance("--quiet", "--vout=gl")
        
        # --- UI ---
        top_bar = ttk.Frame(self.window); top_bar.pack(side="top", fill="x", padx=10, pady=5)
        ttk.Button(top_bar, text="Administrar Cámaras", command=self.open_settings).pack(side="left")

        self.grid_frame = ttk.Frame(self.window); self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.bottom_bar = ttk.Frame(self.window); self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)
        self.prev_button = ttk.Button(self.bottom_bar, text="<< Anterior", command=self.prev_page); self.prev_button.pack(side="left")
        self.page_label = ttk.Label(self.bottom_bar, text="Página 0 de 0", anchor="center"); self.page_label.pack(side="left", fill="x", expand=True)
        self.next_button = ttk.Button(self.bottom_bar, text="Siguiente >>", command=self.next_page); self.next_button.pack(side="right")
        
        self.fullscreen_frame = ttk.Frame(self.window)
        self.fullscreen_label = ttk.Label(self.fullscreen_frame, text="", font=("Helvetica", 14, "bold"))
        
        self.fs_controls_frame = ttk.Frame(self.fullscreen_frame)
        
        self.fullscreen_video_frame = tk.Frame(self.fullscreen_frame, bg="black")
        
        # --- CAMBIO: Cambiar el orden de empaquetado ---
        self.fullscreen_label.pack(pady=(5,0))
        self.fs_controls_frame.pack(pady=5) # <-- Controles ahora van aquí
        self.fullscreen_video_frame.pack(fill="both", expand=True) # <-- Video llena el resto
        
        # --- El resto de la configuración de los botones ---
        self.fs_back_button = ttk.Button(self.fs_controls_frame, text="Volver a la Cuadrícula", command=self.exit_fullscreen)
        self.fs_back_button.pack(side="left", padx=5)
        
        self.fs_audio_button = ttk.Button(self.fs_controls_frame, text="🔇", width=3, command=self._toggle_fullscreen_audio)
        self.fs_audio_button.pack(side="left", padx=5)
        
        self.fs_reload_button = ttk.Button(self.fs_controls_frame, text="🔄", width=3, command=self._reload_fullscreen_stream)
        self.fs_reload_button.pack(side="left", padx=5)

        self.fs_enter_true_fullscreen_button = ttk.Button(self.fs_controls_frame, text="Pantalla Completa", command=self.enter_true_fullscreen)
        self.fs_enter_true_fullscreen_button.pack(side="left", padx=5)

        # Este botón se crea pero no se empaqueta, aparecerá solo en modo pantalla completa real
        self.fs_exit_true_fullscreen_button = ttk.Button(self.fs_controls_frame, text="Salir de Pantalla Completa", command=self.exit_true_fullscreen)
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_page_view()
        self.window.mainloop()

    def update_page_view(self):
        self.stop_all_streams()
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        
        self.audio_buttons.clear()
        self.overlay_buttons.clear()
        self.camera_video_frames.clear()

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
            
            video_frame = tk.Frame(pane, bg="black", width=CAM_FRAME_WIDTH, height=CAM_FRAME_HEIGHT)
            video_frame.pack(fill="both", expand=True)

            if global_index < self.num_total_cameras:
                url = self.all_camera_urls[global_index]
                pane.config(text=self._extract_name_from_url(url, default_name=f"Cámara {global_index+1}"))
                self.camera_video_frames[global_index] = video_frame
                
                button_overlay_frame = ttk.Frame(pane)
                self.overlay_buttons[global_index] = button_overlay_frame

                audio_button = ttk.Button(button_overlay_frame, text="🔇", width=3, command=lambda idx=global_index: self.toggle_audio_for_camera(idx))
                audio_button.pack(side="left")
                self.audio_buttons[global_index] = audio_button
                
                expand_button = ttk.Button(button_overlay_frame, text="⛶", width=3, command=lambda idx=global_index: self.enter_fullscreen(idx))
                expand_button.pack(side="left", padx=(5,0))
                
                reload_button = ttk.Button(button_overlay_frame, text="🔄", width=3, command=lambda idx=global_index: self.reload_grid_stream(idx))
                reload_button.pack(side="left", padx=(5,0))

                pane.bind("<Enter>", lambda e, idx=global_index: self.show_overlay_buttons(idx))
                pane.bind("<Leave>", lambda e, idx=global_index: self.hide_overlay_buttons(idx))
                
                self.start_stream(global_index, url, video_frame, use_substream=True)

    def show_overlay_buttons(self, global_index):
        if global_index in self.overlay_buttons:
            self.overlay_buttons[global_index].place(relx=1.0, y=5, x=-5, anchor="ne")

    def hide_overlay_buttons(self, global_index):
        if global_index in self.overlay_buttons:
            self.overlay_buttons[global_index].place_forget()

    def start_stream(self, global_index, url, frame_widget, use_substream=False):
        if global_index in self.active_players: return

        stream_url = url
        if use_substream:
            stream_url = url.replace("stream1", "stream2")

        player = self.vlc_instance.media_player_new()
        media = self.vlc_instance.media_new(stream_url)
        media.add_option(':rtsp-tcp')
        player.set_media(media)
        player.set_hwnd(frame_widget.winfo_id())
        player.audio_set_mute(True)
        player.play()
        self.active_players[global_index] = player

    def toggle_audio_for_camera(self, global_index):
        if self.audio_source_index is not None and self.audio_source_index in self.active_players:
            self.active_players[self.audio_source_index].audio_set_mute(True)
            if self.audio_source_index in self.audio_buttons:
                self.audio_buttons[self.audio_source_index].config(text="🔇")
        
        if self.audio_source_index == global_index:
            self.audio_source_index = None
        else:
            if global_index in self.active_players:
                self.active_players[global_index].audio_set_mute(False)
                self.audio_source_index = global_index
                if global_index in self.audio_buttons:
                    self.audio_buttons[global_index].config(text="🔊")

    def reload_grid_stream(self, global_index):
        if global_index in self.active_players:
            self.active_players[global_index].stop()
            self.active_players[global_index].release()
            del self.active_players[global_index]
        
        url = self.all_camera_urls[global_index]
        video_frame = self.overlay_buttons[global_index].master.winfo_children()[0]
        self.start_stream(global_index, url, video_frame, use_substream=True)

    def _play_fullscreen(self, global_index):
        if self.fullscreen_player:
            self.fullscreen_player.stop()
            self.fullscreen_player.release()

        url = self.all_camera_urls[global_index]
        self.fullscreen_player = self.vlc_instance.media_player_new()
        media = self.vlc_instance.media_new(url)
        media.add_option(':rtsp-tcp')
        self.fullscreen_player.set_media(media)
        self.fullscreen_player.set_hwnd(self.fullscreen_video_frame.winfo_id())
        
        is_audio_active = (self.audio_source_index == global_index)
        self.fullscreen_player.audio_set_mute(not is_audio_active)
        self.fs_audio_button.config(text="🔊" if is_audio_active else "🔇")
        
        self.fullscreen_player.play()
    
    def _toggle_fullscreen_audio(self):
        if self.fullscreen_camera_index is None: return
        self.toggle_audio_for_camera(self.fullscreen_camera_index)
        is_audio_active = (self.audio_source_index == self.fullscreen_camera_index)
        self.fs_audio_button.config(text="🔊" if is_audio_active else "🔇")
        if self.fullscreen_player:
            self.fullscreen_player.audio_set_mute(not is_audio_active)

    def _reload_fullscreen_stream(self):
        if self.fullscreen_camera_index is None: return
        self._play_fullscreen(self.fullscreen_camera_index)

    def enter_fullscreen(self, global_index):
        if global_index in self.active_players:
            self.active_players[global_index].stop()
            self.active_players[global_index].release()
            del self.active_players[global_index]
            
        self.fullscreen_mode = True
        self.fullscreen_camera_index = global_index
        self._update_fullscreen_info()
        
        self.grid_frame.pack_forget()
        self.bottom_bar.pack_forget()
        self.fullscreen_frame.pack(fill="both", expand=True)
        
        self._play_fullscreen(global_index)
        
        self.window.bind("<Escape>", self.handle_escape)
        self.window.bind("<Right>", self.next_camera_fullscreen)
        self.window.bind("<Left>", self.prev_camera_fullscreen)

    def exit_fullscreen(self, event=None):
        if self.true_fullscreen: self.exit_true_fullscreen()
        
        if self.fullscreen_player:
            self.fullscreen_player.stop()
            self.fullscreen_player.release()
            self.fullscreen_player = None
        
        self.fullscreen_mode = False
        self.fullscreen_camera_index = None
        
        self.fullscreen_frame.pack_forget()
        
        self.window.unbind("<Escape>")
        self.window.unbind("<Right>")
        self.window.unbind("<Left>")
        
        self.update_page_view()
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.bottom_bar.pack(side="bottom", fill="x", padx=10, pady=10)

    def _show_fullscreen_controls(self, event=None):
        self.fs_controls_frame.pack(pady=5)
        if self.hide_controls_job:
            self.window.after_cancel(self.hide_controls_job)
        self.hide_controls_job = self.window.after(3000, self._hide_fullscreen_controls)

    def _hide_fullscreen_controls(self):
        self.fs_controls_frame.pack_forget()

    def enter_true_fullscreen(self, event=None):
        self.true_fullscreen = True
        self.window.attributes('-fullscreen', True)
        self._hide_fullscreen_controls()
        self.window.bind("<Motion>", self._show_fullscreen_controls)

    def exit_true_fullscreen(self, event=None):
        self.true_fullscreen = False
        self.window.attributes('-fullscreen', False)
        if self.hide_controls_job:
            self.window.after_cancel(self.hide_controls_job)
            self.hide_controls_job = None
        self._show_fullscreen_controls()
        self.window.unbind("<Motion>")
        
    def handle_escape(self, event=None):
        if self.true_fullscreen:
            self.exit_true_fullscreen()
        else:
            self.exit_fullscreen()
            
    def _update_fullscreen_info(self):
        if self.fullscreen_camera_index is not None:
            camera_name = self._extract_name_from_url(self.all_camera_urls[self.fullscreen_camera_index], default_name=f"CÁMARA {self.fullscreen_camera_index+1}")
            self.fullscreen_label.config(text=f"{camera_name} - VISTA COMPLETA")

    def next_camera_fullscreen(self, event=None):
        if self.num_total_cameras <= 1: return
        self.fullscreen_camera_index = (self.fullscreen_camera_index + 1) % self.num_total_cameras
        self._update_fullscreen_info()
        self._play_fullscreen(self.fullscreen_camera_index)

    def prev_camera_fullscreen(self, event=None):
        if self.num_total_cameras <= 1: return
        self.fullscreen_camera_index = (self.fullscreen_camera_index - 1 + self.num_total_cameras) % self.num_total_cameras
        self._update_fullscreen_info()
        self._play_fullscreen(self.fullscreen_camera_index)

    def on_closing(self):
        self.stop_all_streams()
        self.window.after(100, self.window.destroy)

    def stop_all_streams(self):
        if self.fullscreen_player:
            self.fullscreen_player.stop()
            self.fullscreen_player.release()
            self.fullscreen_player = None
            
        for player in self.active_players.values():
            player.stop()
            player.release()
        self.active_players.clear()
        self.audio_source_index = None
    
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
    app = CameraViewerApp(root, "Visor de Cámaras con Audio Selectivo")