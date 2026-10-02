import socket
from threading import Thread
import tkinter as tk
from tkinter import scrolledtext, messagebox
import datetime
import struct
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

HOST = "127.0.0.1"
TCP_PORT = 5678
UDP_PORT = 5679
BUFFER_SIZE = 256
INITIAL = b"TCP TEST\n"
LARGE_MSG_MAGIC = b'\xDE\xAD\xBE\xEF'

# Encryption - must match server!
SHARED_PASSWORD = b"MySecretPassword123"

class CryptoHelper:
    """Helper class for encryption/decryption"""
    
    @staticmethod
    def generate_key_from_password(password):
        """Generate encryption key from password"""
        salt = b'salt_1234567890'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    @staticmethod
    def create_cipher(password):
        """Create Fernet cipher from password"""
        key = CryptoHelper.generate_key_from_password(password)
        return Fernet(key)

class EncryptedHybridClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🔒 Encrypted Hybrid Chat Client")
        self.root.geometry("700x600")
        self.root.configure(bg='#2c3e50')
        
        self.tcp_sock = None
        self.udp_sock = None
        self.connected = False
        self.client_id = None
        self.typing_timer = None
        self.cipher = None
        
        # Title
        title_frame = tk.Frame(root, bg='#34495e', pady=10)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="🔒 Encrypted Hybrid Chat", font=("Arial", 16, "bold"), 
                bg='#34495e', fg='white').pack()
        tk.Label(title_frame, text="AES-256 Encryption Enabled", font=("Arial", 9), 
                bg='#34495e', fg='#3498db').pack()
        
        # Connection Frame
        conn_frame = tk.Frame(root, bg='#2c3e50', pady=10)
        conn_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(conn_frame, text="Host:", bg='#2c3e50', fg='white').pack(side=tk.LEFT, padx=5)
        self.host_entry = tk.Entry(conn_frame, width=12)
        self.host_entry.insert(0, HOST)
        self.host_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(conn_frame, text="TCP:", bg='#2c3e50', fg='white').pack(side=tk.LEFT)
        self.tcp_port_entry = tk.Entry(conn_frame, width=5)
        self.tcp_port_entry.insert(0, str(TCP_PORT))
        self.tcp_port_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(conn_frame, text="UDP:", bg='#2c3e50', fg='white').pack(side=tk.LEFT)
        self.udp_port_entry = tk.Entry(conn_frame, width=5)
        self.udp_port_entry.insert(0, str(UDP_PORT))
        self.udp_port_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(conn_frame, text="🔑 Pass:", bg='#2c3e50', fg='white').pack(side=tk.LEFT, padx=5)
        self.password_entry = tk.Entry(conn_frame, width=15, show="*")
        self.password_entry.insert(0, SHARED_PASSWORD.decode())
        self.password_entry.pack(side=tk.LEFT, padx=5)
        
        self.connect_btn = tk.Button(conn_frame, text="Connect", command=self.connect,
                                     bg='#27ae60', fg='white', font=("Arial", 10, "bold"),
                                     padx=15)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_btn = tk.Button(conn_frame, text="Disconnect", command=self.disconnect,
                                       bg='#e74c3c', fg='white', font=("Arial", 10, "bold"),
                                       padx=15, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        # Status Frame
        status_frame = tk.Frame(root, bg='#2c3e50', pady=5)
        status_frame.pack(fill=tk.X, padx=10)
        
        self.tcp_status = tk.Label(status_frame, text="TCP: Disconnected", bg='#2c3e50', 
                                   fg='#e74c3c', font=("Arial", 9))
        self.tcp_status.pack(side=tk.LEFT, padx=10)
        
        self.udp_status = tk.Label(status_frame, text="UDP: Inactive", bg='#2c3e50', 
                                   fg='#e74c3c', font=("Arial", 9))
        self.udp_status.pack(side=tk.LEFT, padx=10)
        
        self.crypto_status = tk.Label(status_frame, text="🔒 Encrypted", bg='#2c3e50', 
                                     fg='#3498db', font=("Arial", 9, "bold"))
        self.crypto_status.pack(side=tk.LEFT, padx=10)
        
        self.typing_indicator = tk.Label(status_frame, text="", bg='#2c3e50', 
                                        fg='#95a5a6', font=("Arial", 9, "italic"))
        self.typing_indicator.pack(side=tk.LEFT, padx=10)
        
        # Chat Display
        chat_frame = tk.Frame(root, bg='#2c3e50')
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        tk.Label(chat_frame, text="Messages (End-to-End Encrypted):", bg='#2c3e50', fg='white', 
                font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        self.chat_display = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, 
                                                      state=tk.DISABLED, height=15,
                                                      bg='#ecf0f1', font=("Arial", 10))
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Input Frame
        input_frame = tk.Frame(root, bg='#2c3e50', pady=10)
        input_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(input_frame, text="Message:", bg='#2c3e50', fg='white').pack(side=tk.LEFT, padx=5)
        
        self.message_entry = tk.Entry(input_frame, font=("Arial", 10))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        self.message_entry.bind('<KeyPress>', self.on_typing)
        self.message_entry.config(state=tk.DISABLED)
        
        self.send_btn = tk.Button(input_frame, text="🔒 Send Encrypted", command=self.send_message,
                                 bg='#3498db', fg='white', font=("Arial", 10, "bold"),
                                 padx=20, state=tk.DISABLED)
        self.send_btn.pack(side=tk.LEFT, padx=5)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def connect(self):
        try:
            host = self.host_entry.get()
            tcp_port = int(self.tcp_port_entry.get())
            udp_port = int(self.udp_port_entry.get())
            password = self.password_entry.get().encode()
            
            # Initialize encryption
            self.cipher = CryptoHelper.create_cipher(password)
            self.add_message("CRYPTO", "🔒 Encryption initialized with AES-256")
            
            # Connect TCP
            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.connect((host, tcp_port))
            self.connected = True
            
            # Setup UDP
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_udp_addr = (host, udp_port)
            
            # Send encrypted initial message
            encrypted_initial = self.cipher.encrypt(INITIAL)
            self.tcp_sock.sendall(encrypted_initial)
            self.add_message("SYSTEM", "Connected to TCP server")
            self.add_message("SENT", INITIAL.decode(errors='replace').strip())
            
            # Receive encrypted response
            encrypted_response = self.tcp_sock.recv(BUFFER_SIZE * 2)
            decrypted_response = self.cipher.decrypt(encrypted_response)
            response_text = decrypted_response.decode(errors='replace').strip()
            self.add_message("RECEIVED", response_text)
            
            self.client_id = 1
            
            # Update UI
            self.tcp_status.config(text="TCP: Connected 🔒", fg='#27ae60')
            self.udp_status.config(text="UDP: Active 🔒", fg='#27ae60')
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.message_entry.config(state=tk.NORMAL)
            self.send_btn.config(state=tk.NORMAL)
            self.host_entry.config(state=tk.DISABLED)
            self.tcp_port_entry.config(state=tk.DISABLED)
            self.udp_port_entry.config(state=tk.DISABLED)
            self.password_entry.config(state=tk.DISABLED)
            
            # Start threads
            Thread(target=self.receive_tcp, daemon=True).start()
            Thread(target=self.receive_udp, daemon=True).start()
            Thread(target=self.send_heartbeat, daemon=True).start()
            
            self.add_message("CRYPTO", "🔒 All communications are encrypted")
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
    
    def disconnect(self):
        self.connected = False
        if self.tcp_sock:
            self.tcp_sock.close()
        if self.udp_sock:
            self.udp_sock.close()
        
        self.add_message("SYSTEM", "Disconnected from server")
        self.tcp_status.config(text="TCP: Disconnected", fg='#e74c3c')
        self.udp_status.config(text="UDP: Inactive", fg='#e74c3c')
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.message_entry.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)
        self.host_entry.config(state=tk.NORMAL)
        self.tcp_port_entry.config(state=tk.NORMAL)
        self.udp_port_entry.config(state=tk.NORMAL)
        self.password_entry.config(state=tk.NORMAL)
    
    def send_message(self):
        """Send encrypted message via TCP"""
        message = self.message_entry.get()
        if message and self.connected:
            try:
                self.send_udp_packet("STOP_TYPING", "")
                
                message_with_newline = message + "\n"
                encrypted = self.cipher.encrypt(message_with_newline.encode())
                
                if len(encrypted) > BUFFER_SIZE:
                    self.add_message("SYSTEM", f"Sending large encrypted message ({len(encrypted)} bytes)...")
                    self.send_encrypted_message_with_length(message_with_newline)
                else:
                    self.tcp_sock.sendall(encrypted)
                
                self.add_message("SENT", f"🔒 {message}")
                self.message_entry.delete(0, tk.END)
            except Exception as e:
                self.add_message("ERROR", f"Failed to send: {str(e)}")
                self.disconnect()
    
    def send_encrypted_message_with_length(self, message):
        """Send large encrypted message with length prefix"""
        encrypted = self.cipher.encrypt(message.encode())
        message_length = len(encrypted)
        
        self.tcp_sock.sendall(LARGE_MSG_MAGIC)
        length_prefix = struct.pack('!I', message_length)
        self.tcp_sock.sendall(length_prefix)
        
        sent = 0
        while sent < message_length:
            chunk_size = min(BUFFER_SIZE, message_length - sent)
            chunk = encrypted[sent:sent + chunk_size]
            self.tcp_sock.sendall(chunk)
            sent += chunk_size
    
    def on_typing(self, event):
        """Handle typing - send encrypted UDP indicator"""
        if not self.connected:
            return
        
        if self.typing_timer:
            self.root.after_cancel(self.typing_timer)
        
        self.send_udp_packet("TYPING", "")
        self.typing_timer = self.root.after(2000, lambda: self.send_udp_packet("STOP_TYPING", ""))
    
    def send_udp_packet(self, msg_type, data):
        """Send encrypted UDP packet"""
        if self.connected and self.udp_sock and self.client_id:
            try:
                message = f"{self.client_id}:{msg_type}:{data}"
                encrypted = self.cipher.encrypt(message.encode())
                self.udp_sock.sendto(encrypted, self.server_udp_addr)
            except Exception as e:
                print(f"UDP send error: {e}")
    
    def send_heartbeat(self):
        """Send encrypted UDP heartbeat"""
        while self.connected:
            self.send_udp_packet("HEARTBEAT", "")
            time.sleep(3)
    
    def recv_exact(self, num_bytes):
        """Receive exactly num_bytes"""
        data = b''
        while len(data) < num_bytes:
            chunk = self.tcp_sock.recv(num_bytes - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data
    
    def receive_encrypted_message_with_length(self):
        """Receive large encrypted message"""
        length_bytes = self.recv_exact(4)
        message_length = struct.unpack('!I', length_bytes)[0]
        encrypted_bytes = self.recv_exact(message_length)
        decrypted = self.cipher.decrypt(encrypted_bytes)
        return decrypted
    
    def receive_tcp(self):
        """Receive encrypted TCP messages"""
        receive_buffer = b''
        
        try:
            while self.connected:
                try:
                    self.tcp_sock.setblocking(True)
                    
                    peek_data = b''
                    attempts = 0
                    while len(peek_data) < 4 and attempts < 100:
                        try:
                            peek_data = self.tcp_sock.recv(4, socket.MSG_PEEK)
                            if not peek_data:
                                self.add_message("SYSTEM", "Server closed connection")
                                self.root.after(0, self.disconnect)
                                return
                            if len(peek_data) < 4:
                                time.sleep(0.001)
                                attempts += 1
                            else:
                                break
                        except BlockingIOError:
                            time.sleep(0.001)
                            attempts += 1
                    
                    if len(peek_data) >= 4 and peek_data[:4] == LARGE_MSG_MAGIC:
                        self.recv_exact(4)
                        decrypted = self.receive_encrypted_message_with_length()
                        text = decrypted.decode(errors='replace').strip()
                        if text:
                            self.add_message("RECEIVED", f"🔒 {text}")
                    else:
                        encrypted_chunk = self.tcp_sock.recv(BUFFER_SIZE * 2)
                        
                        if not encrypted_chunk:
                            self.add_message("SYSTEM", "Server closed connection")
                            self.root.after(0, self.disconnect)
                            break
                        
                        # Decrypt
                        try:
                            decrypted = self.cipher.decrypt(encrypted_chunk)
                            receive_buffer += decrypted
                            
                            if b'\n' in receive_buffer:
                                lines = receive_buffer.split(b'\n')
                                receive_buffer = lines[-1]
                                
                                for line in lines[:-1]:
                                    text = line.decode(errors='replace').strip()
                                    if text:
                                        self.add_message("RECEIVED", f"🔒 {text}")
                        except Exception as e:
                            print(f"Decryption error: {e}")
                
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.connected:
                        raise e
                    break
                
        except Exception as e:
            if self.connected:
                self.add_message("ERROR", f"TCP error: {str(e)}")
                self.root.after(0, self.disconnect)
    
    def receive_udp(self):
        """Receive encrypted UDP messages"""
        while self.connected:
            try:
                encrypted_data, addr = self.udp_sock.recvfrom(BUFFER_SIZE * 2)
                
                # Decrypt
                decrypted = self.cipher.decrypt(encrypted_data)
                message = decrypted.decode(errors='replace').strip()
                
                if message.startswith("TYPING:"):
                    client_id = message.split(':')[1]
                    self.typing_indicator.config(text=f"Client {client_id} is typing...")
                
                elif message.startswith("STOP_TYPING:"):
                    self.typing_indicator.config(text="")
                
                elif message.startswith("PONG:"):
                    self.add_message("UDP", "🔒 Encrypted pong received")
                
                else:
                    self.add_message("UDP", f"🔒 {message}")
            
            except Exception as e:
                if self.connected:
                    print(f"UDP receive error: {e}")
    
    def add_message(self, msg_type, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        self.chat_display.config(state=tk.NORMAL)
        
        if msg_type == "SENT":
            self.chat_display.insert(tk.END, f"[{timestamp}] You: {message}\n", "sent")
            self.chat_display.tag_config("sent", foreground="#2980b9", font=("Arial", 10, "bold"))
        elif msg_type == "RECEIVED":
            self.chat_display.insert(tk.END, f"[{timestamp}] Server: {message}\n", "received")
            self.chat_display.tag_config("received", foreground="#27ae60", font=("Arial", 10))
        elif msg_type == "UDP":
            self.chat_display.insert(tk.END, f"[{timestamp}] [UDP] {message}\n", "udp")
            self.chat_display.tag_config("udp", foreground="#9b59b6", font=("Arial", 10))
        elif msg_type == "CRYPTO":
            self.chat_display.insert(tk.END, f"[{timestamp}] {message}\n", "crypto")
            self.chat_display.tag_config("crypto", foreground="#3498db", font=("Arial", 10, "bold"))
        elif msg_type == "SYSTEM":
            self.chat_display.insert(tk.END, f"[{timestamp}] {message}\n", "system")
            self.chat_display.tag_config("system", foreground="#7f8c8d", font=("Arial", 10, "italic"))
        elif msg_type == "ERROR":
            self.chat_display.insert(tk.END, f"[{timestamp}] ERROR: {message}\n", "error")
            self.chat_display.tag_config("error", foreground="#e74c3c", font=("Arial", 10, "bold"))
        
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def on_closing(self):
        if self.connected:
            self.disconnect()
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = EncryptedHybridClientGUI(root)
    root.mainloop()