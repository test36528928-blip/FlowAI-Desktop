# -*- coding: utf-8 -*-
import os
import sqlite3
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from google import genai

APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FlowAI"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = str(APP_DATA_DIR / "flowai_storage.db")
MODEL_NAME = "gemini-3.8-flash"

def initialize_database():
    """Create the local database and default settings on first launch."""
    with sqlite3.connect(DB_PATH, timeout=15) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "chat_id INTEGER NOT NULL, sender TEXT NOT NULL, content TEXT NOT NULL, "
            "FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS instructions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL, content TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 0)"
        )
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('theme', 'light')")

# ------------------ VERİTABANI İŞLEMLERİ ------------------
def db_query(query, params=(), commit=False, fetchall=False, fetchone=False):
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = None
    if commit:
        conn.commit()
    if fetchall:
        result = cursor.fetchall()
    elif fetchone:
        result = cursor.fetchone()
    conn.close()
    return result

# ------------------ FLOWAI MASAÜSTÜ SINIFI ------------------
class FlowAIDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FlowAI Desktop Assistant")
        self.geometry("1100x700")
        self.minsize(800, 550)

        # API İstemci Kurulumu
        self.api_key = os.environ.get("GOOGLE_API_KEY", "")
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)

        self.active_chat_id = None
        theme_row = db_query("SELECT value FROM settings WHERE key='theme'", fetchone=True)
        self.current_theme = theme_row[0] if theme_row else "light"

        self.setup_styles()
        self.build_ui()
        self.load_chats()
        self.load_instructions()

        if not self.api_key:
            self.after(250, self.configure_api_key)

    def configure_api_key(self):
        key = simpledialog.askstring(
            "Gemini API Anahtarı",
            "Google Gemini API anahtarını girin. Anahtar bu oturum boyunca bellekte tutulur ve dosyaya kaydedilmez:",
            parent=self, show="*"
        )
        if not key or not key.strip():
            return
        try:
            candidate = genai.Client(api_key=key.strip())
            self.client = candidate
            self.api_key = key.strip()
            messagebox.showinfo("FlowAI", "API anahtarı bu oturum için ayarlandı.", parent=self)
        except Exception as exc:
            self.client = None
            self.api_key = ""
            messagebox.showerror("API Anahtarı", f"API istemcisi oluşturulamadı: {exc}", parent=self)

    def setup_styles(self):
        self.style = ttk.Style()
        if self.current_theme == 'dark':
            self.bg_color = "#1e1e2e"
            self.fg_color = "#ffffff"
            self.sidebar_color = "#11111b"
            self.chat_bg = "#181825"
            self.bubble_user = "#313244"
            self.bubble_ai = "#45475a"
        else:
            self.bg_color = "#f2f2f7"
            self.fg_color = "#000000"
            self.sidebar_color = "#e5e5ea"
            self.chat_bg = "#ffffff"
            self.bubble_user = "#007aff"
            self.bubble_ai = "#e5e5ea"

        self.configure(bg=self.bg_color)

    def build_ui(self):
        # Ana Grid Dağılımı
        self.grid_columnconfigure(0, weight=1) # Sidebar
        self.grid_columnconfigure(1, weight=4) # Chat Area
        self.grid_rowconfigure(0, weight=1)

        # 1. Kenar Çubuğu (Sidebar)
        self.sidebar = tk.Frame(self, bg=self.sidebar_color, width=250)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.sidebar.grid_propagate(False)

        # Yeni Sohbet Butonu
        self.btn_new_chat = tk.Button(
            self.sidebar, text="+ Yeni Sohbet", bg="#22c55e", fg="white",
            font=("Arial", 11, "bold"), relief="flat", command=self.new_chat
        )
        self.btn_new_chat.pack(fill="x", padx=10, pady=10)

        # Sohbet Listesi
        self.lbl_history = tk.Label(self.sidebar, text="Sohbet Geçmişi", bg=self.sidebar_color, fg=self.fg_color, font=("Arial", 10, "bold"))
        self.lbl_history.pack(anchor="w", padx=10, pady=5)

        self.chat_listbox = tk.Listbox(self.sidebar, bg=self.sidebar_color, fg=self.fg_color, bd=0, highlightthickness=0, font=("Arial", 10))
        self.chat_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        self.chat_listbox.bind("<<ListboxSelect>>", self.on_chat_selected)

        # Sidebar Alt Kontroller (Ayarlar, Silme, Tema)
        self.btn_delete_chat = tk.Button(self.sidebar, text="Sohbeti Sil", bg="#ef4444", fg="white", relief="flat", command=self.delete_current_chat)
        self.btn_delete_chat.pack(fill="x", padx=10, pady=2)

        self.btn_clear_all = tk.Button(self.sidebar, text="Tüm Geçmişi Temizle", bg="#991b1b", fg="white", relief="flat", command=self.clear_all_chats)
        self.btn_clear_all.pack(fill="x", padx=10, pady=2)

        # 2. Sohbet ve Mesajlaşma Ekranı
        self.chat_frame = tk.Frame(self, bg=self.bg_color)
        self.chat_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.chat_frame.grid_columnconfigure(0, weight=1)
        self.chat_frame.grid_rowconfigure(1, weight=1) # Chat display area

        # Üst Bilgi Barı
        self.top_bar = tk.Frame(self.chat_frame, bg=self.bg_color)
        self.top_bar.grid(row=0, column=0, sticky="ew", pady=5)

        self.lbl_chat_title = tk.Label(self.top_bar, text="FlowAI Chatbot", font=("Arial", 14, "bold"), bg=self.bg_color, fg=self.fg_color)
        self.lbl_chat_title.pack(side="left", padx=5)

        # Tema, API anahtarı ve talimatlar kontrolleri
        self.btn_theme = tk.Button(self.top_bar, text="Tema Değiştir", command=self.toggle_theme, relief="groove")
        self.btn_theme.pack(side="right", padx=5)

        self.btn_api_key = tk.Button(self.top_bar, text="API Anahtarı", command=self.configure_api_key, relief="groove")
        self.btn_api_key.pack(side="right", padx=5)

        self.btn_instructions = tk.Button(self.top_bar, text="Sistem Talimatları", command=self.open_instructions_window, relief="groove")
        self.btn_instructions.pack(side="right", padx=5)

        # Sohbet İçeriği Görüntüleme Alanı (Text widget)
        self.chat_display = tk.Text(
            self.chat_frame, bg=self.chat_bg, fg=self.fg_color, state="disabled",
            wrap="word", font=("Arial", 11), bd=1, relief="solid"
        )
        self.chat_display.grid(row=1, column=0, sticky="nsew", pady=5)

        # Giriş Paneli (Mesaj Yazma Alanı)
        self.input_panel = tk.Frame(self.chat_frame, bg=self.bg_color)
        self.input_panel.grid(row=2, column=0, sticky="ew", pady=5)
        self.input_panel.grid_columnconfigure(0, weight=1)

        self.entry_message = tk.Text(self.input_panel, height=3, font=("Arial", 11), wrap="word")
        self.entry_message.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.entry_message.bind("<Return>", self.on_enter_pressed)
        self.entry_message.bind("<Shift-Return>", lambda e: "")

        self.btn_send = tk.Button(
            self.input_panel, text="Gönder", bg="#3b82f6", fg="white",
            font=("Arial", 11, "bold"), width=10, command=self.send_message
        )
        self.btn_send.grid(row=0, column=1, sticky="ns")

    # ------------------ FONKSİYONLAR & OLAYLAR ------------------
    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        db_query("UPDATE settings SET value=? WHERE key='theme'", (self.current_theme,), commit=True)
        self.setup_styles()
        self.sidebar.configure(bg=self.sidebar_color)
        self.lbl_history.configure(bg=self.sidebar_color, fg=self.fg_color)
        self.chat_listbox.configure(bg=self.sidebar_color, fg=self.fg_color)
        self.chat_frame.configure(bg=self.bg_color)
        self.top_bar.configure(bg=self.bg_color)
        self.lbl_chat_title.configure(bg=self.bg_color, fg=self.fg_color)
        self.chat_display.configure(bg=self.chat_bg, fg=self.fg_color)
        self.input_panel.configure(bg=self.bg_color)

    def new_chat(self):
        title = f"Yeni Sohbet {int(time.time()) % 1000}"
        db_query("INSERT INTO chats (title) VALUES (?)", (title,), commit=True)
        self.load_chats()
        # En son sohbeti seç
        self.chat_listbox.selection_clear(0, tk.END)
        self.chat_listbox.selection_set(tk.END)
        self.on_chat_selected(None)

    def load_chats(self):
        self.chat_listbox.delete(0, tk.END)
        self.chats_data = db_query("SELECT id, title FROM chats ORDER BY id ASC", fetchall=True)
        for chat in self.chats_data:
            self.chat_listbox.insert(tk.END, chat[1])

    def on_chat_selected(self, event):
        selection = self.chat_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        self.active_chat_id = self.chats_data[idx][0]
        self.lbl_chat_title.config(text=self.chats_data[idx][1])
        self.load_messages()

    def load_messages(self):
        self.chat_display.config(state="normal")
        self.chat_display.delete("1.0", tk.END)
        if self.active_chat_id:
            messages = db_query("SELECT sender, content FROM messages WHERE chat_id=? ORDER BY id ASC", (self.active_chat_id,), fetchall=True)
            for msg in messages:
                sender_prefix = "Siz: " if msg[0] == "user" else "FlowAI: "
                self.chat_display.insert(tk.END, f"{sender_prefix}{msg[1]}\n\n")
        self.chat_display.config(state="disabled")
        self.chat_display.see(tk.END)

    def on_enter_pressed(self, event):
        # Shift+Enter algılanırsa yeni satıra geç
        if event.state & 0x0001:
            return
        self.send_message()
        return "break"

    def send_message(self):
        user_text = self.entry_message.get("1.0", tk.END).strip()
        if not user_text:
            return

        if not self.active_chat_id:
            self.new_chat()

        # Kullanıcı mesajını ekle ve kaydet
        db_query("INSERT INTO messages (chat_id, sender, content) VALUES (?, 'user', ?)", (self.active_chat_id, user_text), commit=True)
        self.entry_message.delete("1.0", tk.END)
        self.load_messages()

        # 'FlowAI düşünüyor...' ibaresini göster
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, "FlowAI düşünüyor...\n")
        self.chat_display.config(state="disabled")
        self.chat_display.see(tk.END)

        # Yanıtı asenkron olarak arka planda getir
        chat_id = self.active_chat_id
        threading.Thread(target=self.fetch_ai_response, args=(user_text, chat_id), daemon=True).start()

    def fetch_ai_response(self, prompt, chat_id):
        # Aktif sistem talimatlarını getir
        active_instructions = db_query("SELECT content FROM instructions WHERE is_active=1", fetchall=True)
        instructions_text = " ".join([inst[0] for inst in active_instructions])

        full_prompt = f"Sistem: Sen FlowAI'sin. {instructions_text} Soru: {prompt}"

        # Selamlaşmalar için yerel hızlı yanıt kontrolü
        local_greetings = {"merhaba": "Merhaba! Nasıl yardımcı olabilirim?", "selam": "Selam! Saygılar.", "nasılsın": "Harikayım, teşekkürler!"}
        cleaned_prompt = prompt.lower().strip()
        if cleaned_prompt in local_greetings:
            time.sleep(0.3) # Doğal bir gecikme hissi
            ai_response = local_greetings[cleaned_prompt]
        else:
            if not self.client:
                ai_response = "Hata: GOOGLE_API_KEY tanımlanmamış."
            else:
                try:
                    response = self.client.models.generate_content(
                        model=MODEL_NAME,
                        contents=full_prompt
                    )
                    ai_response = response.text if response.text else "[Boş Yanıt Alındı]"
                except Exception as e:
                    ai_response = f"Bağlantı Hatası: {str(e)}"

        # Veritabanına yaz ve ekranı güncelle
        try:
            db_query("INSERT INTO messages (chat_id, sender, content) VALUES (?, 'assistant', ?)", (chat_id, ai_response), commit=True)
            self.after(0, self.load_messages)
        except (sqlite3.Error, RuntimeError):
            # The target chat may have been deleted or the window closed while the request ran.
            pass

    def delete_current_chat(self):
        if not self.active_chat_id:
            return
        if messagebox.askyesno("Onay", "Seçili sohbeti kalıcı olarak silmek istiyor musunuz?"):
            db_query("DELETE FROM chats WHERE id=?", (self.active_chat_id,), commit=True)
            self.active_chat_id = None
            self.lbl_chat_title.config(text="FlowAI Chatbot")
            self.load_chats()
            self.load_messages()

    def clear_all_chats(self):
        if messagebox.askyesno("Onay", "Tüm sohbet geçmişini silmek istediğinize emin misiniz?"):
            db_query("DELETE FROM chats", commit=True)
            self.active_chat_id = None
            self.lbl_chat_title.config(text="FlowAI Chatbot")
            self.load_chats()
            self.load_messages()

    # ------------------ SİSTEM TALİMATLARI PENCERESİ ------------------
    def load_instructions(self):
        pass

    def open_instructions_window(self):
        inst_win = tk.Toplevel(self)
        inst_win.title("Özel Sistem Talimatları")
        inst_win.geometry("500x400")

        lbl = tk.Label(inst_win, text="Talimatlar Listesi", font=("Arial", 11, "bold"))
        lbl.pack(pady=5)

        listbox_inst = tk.Listbox(inst_win, height=10)
        listbox_inst.pack(fill="both", expand=True, padx=10, pady=5)

        def populate_inst():
            listbox_inst.delete(0, tk.END)
            self.inst_data = db_query("SELECT id, name, is_active FROM instructions", fetchall=True)
            for inst in self.inst_data:
                status = "[AKTİF]" if inst[2] == 1 else "[PASİF]"
                listbox_inst.insert(tk.END, f"{status} {inst[1]}")

        populate_inst()

        def add_inst():
            name = simpledialog.askstring("Yeni Talimat", "Talimat Adı:", parent=inst_win)
            if name:
                content = simpledialog.askstring("Yeni Talimat", "Uygulanacak Talimat İçeriği:", parent=inst_win)
                if content:
                    db_query("INSERT INTO instructions (name, content) VALUES (?, ?)", (name, content), commit=True)
                    populate_inst()

        def toggle_inst():
            selection = listbox_inst.curselection()
            if selection:
                idx = selection[0]
                inst_id = self.inst_data[idx][0]
                current_status = self.inst_data[idx][2]
                new_status = 0 if current_status == 1 else 1
                db_query("UPDATE instructions SET is_active=? WHERE id=?", (new_status, inst_id), commit=True)
                populate_inst()

        def delete_inst():
            selection = listbox_inst.curselection()
            if selection:
                idx = selection[0]
                inst_id = self.inst_data[idx][0]
                db_query("DELETE FROM instructions WHERE id=?", (inst_id,), commit=True)
                populate_inst()

        btn_frame = tk.Frame(inst_win)
        btn_frame.pack(fill="x", pady=10)

        tk.Button(btn_frame, text="Talimat Ekle", command=add_inst).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Aktif/Pasif Yap", command=toggle_inst).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Sil", command=delete_inst).pack(side="left", padx=10)

if __name__ == "__main__":
    initialize_database()
    app = FlowAIDesktopApp()
    app.mainloop()
