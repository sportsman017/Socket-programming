import socket
import sys
from threading import Thread
import tkinter as tk
from tkinter import scrolledtext, messagebox
import datetime
import struct

HOST = "127.0.0.1"
PORT = 5678
BUFFER_SIZE = 1
INITIAL = b"TCP TEST\n"
LARGE_MSG_MAGIC = b'\xDE\xAD\xBE\xEF'  # Magic bytes to identify large messages

class ClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TCP Chat Client")
        self.root.geometry("600x500")
        self.root.configure(bg='#2c3e50')
        
        self.sock = None
        self.connected = False
        
        # Title
        title_frame = tk.Frame(root, bg='#34495e', pady=10)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="TCP Chat Client", font=("Arial", 16, "bold"), 
                bg='#34495e', fg='white').pack()
        
        # Connection Frame
        conn_frame = tk.Frame(root, bg='#2c3e50', pady=10)
        conn_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(conn_frame, text="Host:", bg='#2c3e50', fg='white').pack(side=tk.LEFT, padx=5)
        self.host_entry = tk.Entry(conn_frame, width=15)
        self.host_entry.insert(0, HOST)
        self.host_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(conn_frame, text="Port:", bg='#2c3e50', fg='white').pack(side=tk.LEFT, padx=5)
        self.port_entry = tk.Entry(conn_frame, width=8)
        self.port_entry.insert(0, str(PORT))
        self.port_entry.pack(side=tk.LEFT, padx=5)
        
        self.connect_btn = tk.Button(conn_frame, text="Connect", command=self.connect,
                                     bg='#27ae60', fg='white', font=("Arial", 10, "bold"),
                                     padx=15)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_btn = tk.Button(conn_frame, text="Disconnect", command=self.disconnect,
                                       bg='#e74c3c', fg='white', font=("Arial", 10, "bold"),
                                       padx=15, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        # Status Label
        self.status_label = tk.Label(root, text="Status: Disconnected", bg='#2c3e50', 
                                    fg='#e74c3c', font=("Arial", 10))
        self.status_label.pack(pady=5)
        
        # Chat Display
        chat_frame = tk.Frame(root, bg='#2c3e50')
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        tk.Label(chat_frame, text="Messages:", bg='#2c3e50', fg='white', 
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
        self.message_entry.config(state=tk.DISABLED)
        
        self.send_btn = tk.Button(input_frame, text="Send", command=self.send_message,
                                 bg='#3498db', fg='white', font=("Arial", 10, "bold"),
                                 padx=20, state=tk.DISABLED)
        self.send_btn.pack(side=tk.LEFT, padx=5)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def connect(self):
        try:
            host = self.host_entry.get()
            port = int(self.port_entry.get())
            
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.connected = True
            
            # Send initial message (old way for compatibility)
            self.sock.sendall(INITIAL)
            self.add_message("SYSTEM", "Connected to server")
            self.add_message("SENT", INITIAL.decode(errors='replace').strip())
            
            # Update UI
            self.status_label.config(text="Status: Connected", fg='#27ae60')
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.message_entry.config(state=tk.NORMAL)
            self.send_btn.config(state=tk.NORMAL)
            self.host_entry.config(state=tk.DISABLED)
            self.port_entry.config(state=tk.DISABLED)
            
            # Start receiving thread
            Thread(target=self.receive_messages, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
    
    def disconnect(self):
        self.connected = False
        if self.sock:
            self.sock.close()
        
        self.add_message("SYSTEM", "Disconnected from server")
        self.status_label.config(text="Status: Disconnected", fg='#e74c3c')
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.message_entry.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)
        self.host_entry.config(state=tk.NORMAL)
        self.port_entry.config(state=tk.NORMAL)
    
    def send_message_with_length(self, message):
        """Send message with length prefix for messages > 256 bytes"""
        message_bytes = message.encode()
        message_length = len(message_bytes)
        
        # Send magic header + 4-byte length prefix
        self.sock.sendall(LARGE_MSG_MAGIC)
        length_prefix = struct.pack('!I', message_length)
        self.sock.sendall(length_prefix)
        
        # Send message in chunks
        sent = 0
        while sent < message_length:
            chunk_size = min(BUFFER_SIZE, message_length - sent)
            chunk = message_bytes[sent:sent + chunk_size]
            self.sock.sendall(chunk)
            sent += chunk_size
    
    def send_message(self):
        message = self.message_entry.get()
        if message and self.connected:
            try:
                message_with_newline = message + "\n"
                message_bytes = message_with_newline.encode()
                
                # Check if message exceeds buffer size
                if len(message_bytes) > BUFFER_SIZE:
                    self.add_message("SYSTEM", f"Sending large message ({len(message_bytes)} bytes)...")
                    self.send_message_with_length(message_with_newline)
                    self.add_message("SYSTEM", "Large message sent, waiting for echo...")
                else:
                    # Small message - send normally for compatibility
                    self.sock.sendall(message_bytes)
                
                self.add_message("SENT", message)
                self.message_entry.delete(0, tk.END)
            except Exception as e:
                self.add_message("ERROR", f"Failed to send: {str(e)}")
                self.disconnect()
    
    def recv_exact(self, num_bytes):
        """Receive exactly num_bytes from socket"""
        data = b''
        while len(data) < num_bytes:
            chunk = self.sock.recv(num_bytes - len(data))
            if not chunk:
                raise ConnectionError("Connection closed while receiving data")
            data += chunk
        return data
    
    def receive_message_with_length(self):
        """Receive message with length prefix (magic already consumed)"""
        # Receive 4-byte length prefix
        length_bytes = self.recv_exact(4)
        message_length = struct.unpack('!I', length_bytes)[0]
        
        # Receive the full message
        message_bytes = self.recv_exact(message_length)
        return message_bytes
    
    def receive_messages(self):
        receive_buffer = b''  # Buffer for accumulating small messages
        
        try:
            # Receive initial response (old way)
            data = self.sock.recv(BUFFER_SIZE)
            if data:
                self.add_message("RECEIVED", data.decode(errors='replace').strip())
            
            # Continue receiving
            while self.connected:
                try:
                    self.sock.setblocking(True)
                    
                    # Try to peek 4 bytes to check for magic header
                    # When BUFFER_SIZE is small, we need to wait for enough data
                    peek_size = 4
                    peek_data = b''
                    
                    # Keep peeking until we have 4 bytes or connection closes
                    attempts = 0
                    while len(peek_data) < 4 and attempts < 100:
                        try:
                            peek_data = self.sock.recv(4, socket.MSG_PEEK)
                            if not peek_data:
                                self.add_message("SYSTEM", "Server closed connection")
                                self.root.after(0, self.disconnect)
                                return
                            if len(peek_data) < 4:
                                # Not enough data yet, wait a tiny bit
                                import time
                                time.sleep(0.001)
                                attempts += 1
                            else:
                                break
                        except BlockingIOError:
                            import time
                            time.sleep(0.001)
                            attempts += 1
                    
                    # Check if it starts with magic header
                    if len(peek_data) >= 4 and peek_data[:4] == LARGE_MSG_MAGIC:
                        # Large message with length prefix
                        # Consume the magic header
                        self.recv_exact(4)
                        # Now receive the length-prefixed message
                        message_bytes = self.receive_message_with_length()
                        message_text = message_bytes.decode(errors='replace').strip()
                        if message_text:
                            self.add_message("RECEIVED", message_text)
                    else:
                        # Normal small message - might need multiple recv calls
                        # Read BUFFER_SIZE bytes at a time and accumulate
                        chunk = self.sock.recv(BUFFER_SIZE)
                        
                        if not chunk:
                            self.add_message("SYSTEM", "Server closed connection")
                            self.root.after(0, self.disconnect)
                            break
                        
                        receive_buffer += chunk
                        
                        # Check if we have a complete message (ends with newline)
                        if b'\n' in receive_buffer:
                            # Split by newline and process complete messages
                            lines = receive_buffer.split(b'\n')
                            # Last element might be incomplete, keep it in buffer
                            receive_buffer = lines[-1]
                            
                            # Process all complete lines
                            for line in lines[:-1]:
                                text = line.decode(errors='replace').strip()
                                if text:
                                    self.add_message("RECEIVED", text)
                
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.connected:
                        raise e
                    break
                
        except Exception as e:
            if self.connected:
                self.add_message("ERROR", f"Connection error: {str(e)}")
                self.root.after(0, self.disconnect)
    
    def add_message(self, msg_type, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        self.chat_display.config(state=tk.NORMAL)
        
        if msg_type == "SENT":
            self.chat_display.insert(tk.END, f"[{timestamp}] You: {message}\n", "sent")
            self.chat_display.tag_config("sent", foreground="#2980b9", font=("Arial", 10, "bold"))
        elif msg_type == "RECEIVED":
            self.chat_display.insert(tk.END, f"[{timestamp}] Server: {message}\n", "received")
            self.chat_display.tag_config("received", foreground="#27ae60", font=("Arial", 10))
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
    app = ClientGUI(root)
    root.mainloop()