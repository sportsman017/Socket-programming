"""
Simple P2P Chat Client
- No discovery server needed
- Just enter peer's IP:Port to connect
- Each peer acts as both client and server
- Direct peer-to-peer messaging
"""

import socket
from threading import Thread
import tkinter as tk
from tkinter import scrolledtext, messagebox
import datetime

class SimplePeerToPeer:
    def __init__(self, root):
        self.root = root
        self.root.title("💬 Simple P2P Chat")
        self.root.geometry("700x600")
        self.root.configure(bg='#2c3e50')
        
        self.my_port = None
        self.username = None
        self.peers = {}  # {peer_addr: socket}
        self.server_socket = None
        self.listening = False
        
        self.setup_gui()
    
    def setup_gui(self):
        # Title
        title_frame = tk.Frame(self.root, bg='#34495e', pady=10)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="💬 Simple P2P Chat", font=("Arial", 16, "bold"), 
                bg='#34495e', fg='white').pack()
        tk.Label(title_frame, text="Direct peer-to-peer - No server needed!", 
                font=("Arial", 9), bg='#34495e', fg='#3498db').pack()
        
        # Setup Frame
        setup_frame = tk.LabelFrame(self.root, text="1️⃣ Setup", bg='#34495e', 
                                    fg='white', font=("Arial", 10, "bold"), padx=10, pady=10)
        setup_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Username
        user_frame = tk.Frame(setup_frame, bg='#34495e')
        user_frame.pack(fill=tk.X, pady=2)
        tk.Label(user_frame, text="Your Name:", bg='#34495e', fg='white', width=12, 
                anchor='w').pack(side=tk.LEFT)
        self.username_entry = tk.Entry(user_frame, width=20)
        self.username_entry.pack(side=tk.LEFT, padx=5)
        
        # My Port
        port_frame = tk.Frame(setup_frame, bg='#34495e')
        port_frame.pack(fill=tk.X, pady=2)
        tk.Label(port_frame, text="Your Port:", bg='#34495e', fg='white', width=12, 
                anchor='w').pack(side=tk.LEFT)
        self.my_port_entry = tk.Entry(port_frame, width=10)
        self.my_port_entry.insert(0, "5000")
        self.my_port_entry.pack(side=tk.LEFT, padx=5)
        
        self.start_btn = tk.Button(setup_frame, text="🚀 Start Listening", 
                                   command=self.start_listening,
                                   bg='#27ae60', fg='white', font=("Arial", 10, "bold"))
        self.start_btn.pack(pady=5)
        
        # Connect Frame
        connect_frame = tk.LabelFrame(self.root, text="2️⃣ Connect to Peer", 
                                      bg='#34495e', fg='white', 
                                      font=("Arial", 10, "bold"), padx=10, pady=10)
        connect_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Peer IP
        ip_frame = tk.Frame(connect_frame, bg='#34495e')
        ip_frame.pack(fill=tk.X, pady=2)
        tk.Label(ip_frame, text="Peer IP:", bg='#34495e', fg='white', width=12, 
                anchor='w').pack(side=tk.LEFT)
        self.peer_ip_entry = tk.Entry(ip_frame, width=15)
        self.peer_ip_entry.insert(0, "127.0.0.1")
        self.peer_ip_entry.pack(side=tk.LEFT, padx=5)
        
        # Peer Port
        peer_port_frame = tk.Frame(connect_frame, bg='#34495e')
        peer_port_frame.pack(fill=tk.X, pady=2)
        tk.Label(peer_port_frame, text="Peer Port:", bg='#34495e', fg='white', width=12, 
                anchor='w').pack(side=tk.LEFT)
        self.peer_port_entry = tk.Entry(peer_port_frame, width=10)
        self.peer_port_entry.insert(0, "5001")
        self.peer_port_entry.pack(side=tk.LEFT, padx=5)
        
        self.connect_btn = tk.Button(connect_frame, text="🔗 Connect to Peer", 
                                     command=self.connect_to_peer,
                                     bg='#3498db', fg='white', font=("Arial", 10, "bold"),
                                     state=tk.DISABLED)
        self.connect_btn.pack(pady=5)
        
        # Status
        self.status_label = tk.Label(self.root, text="Status: Not listening", 
                                     bg='#2c3e50', fg='#e74c3c', font=("Arial", 9, "bold"))
        self.status_label.pack(pady=5)
        
        # Peers List
        peers_frame = tk.LabelFrame(self.root, text="Connected Peers", bg='#2c3e50', 
                                    fg='white', font=("Arial", 9, "bold"))
        peers_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.peers_listbox = tk.Listbox(peers_frame, height=3, bg='#ecf0f1', 
                                        font=("Arial", 9))
        self.peers_listbox.pack(fill=tk.X, padx=5, pady=5)
        
        # Chat Display
        chat_frame = tk.Frame(self.root, bg='#2c3e50')
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        tk.Label(chat_frame, text="Messages:", bg='#2c3e50', fg='white', 
                font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        self.chat_display = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, 
                                                      state=tk.DISABLED, height=10,
                                                      bg='#ecf0f1', font=("Arial", 10))
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Input Frame
        input_frame = tk.Frame(self.root, bg='#2c3e50', pady=10)
        input_frame.pack(fill=tk.X, padx=10)
        
        self.message_entry = tk.Entry(input_frame, font=("Arial", 10), state=tk.DISABLED)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        
        self.send_btn = tk.Button(input_frame, text="📤 Send to All", 
                                 command=self.send_message,
                                 bg='#e67e22', fg='white', font=("Arial", 10, "bold"),
                                 padx=15, state=tk.DISABLED)
        self.send_btn.pack(side=tk.LEFT)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def start_listening(self):
        """Start listening for incoming peer connections"""
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showerror("Error", "Please enter your name")
            return
        
        try:
            self.my_port = int(self.my_port_entry.get())
            self.username = username
            
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.my_port))
            self.server_socket.listen(10)
            
            self.listening = True
            
            # Start accepting connections
            Thread(target=self.accept_connections, daemon=True).start()
            
            # Update UI
            self.status_label.config(text=f"Status: Listening on port {self.my_port} as {username}", 
                                    fg='#27ae60')
            self.start_btn.config(state=tk.DISABLED)
            self.connect_btn.config(state=tk.NORMAL)
            self.message_entry.config(state=tk.NORMAL)
            self.send_btn.config(state=tk.NORMAL)
            self.username_entry.config(state=tk.DISABLED)
            self.my_port_entry.config(state=tk.DISABLED)
            
            # Get and display local IP
            local_ip = socket.gethostbyname(socket.gethostname())
            self.add_message("SYSTEM", f"🎉 You're now listening!")
            self.add_message("SYSTEM", f"📍 Your address: {local_ip}:{self.my_port}")
            self.add_message("SYSTEM", f"💡 Share this with friends to let them connect to you!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start listening: {str(e)}")
    
    def accept_connections(self):
        """Accept incoming peer connections"""
        while self.listening:
            try:
                conn, addr = self.server_socket.accept()
                Thread(target=self.handle_new_peer, args=(conn, addr), daemon=True).start()
            except:
                break
    
    def handle_new_peer(self, conn, addr):
        """Handle new incoming peer connection"""
        try:
            # Receive peer's username
            data = conn.recv(1024).decode()
            if data.startswith("HELLO:"):
                peer_username = data.split(':')[1]
                
                # Send our username back
                conn.send(f"HELLO:{self.username}".encode())
                
                # Store peer
                peer_key = f"{peer_username}@{addr[0]}:{addr[1]}"
                self.peers[peer_key] = {'socket': conn, 'username': peer_username, 'addr': addr}
                
                self.add_message("SYSTEM", f"✅ {peer_username} connected from {addr[0]}:{addr[1]}")
                self.update_peers_list()
                
                # Listen for messages from this peer
                Thread(target=self.receive_from_peer, args=(peer_key,), daemon=True).start()
                
        except Exception as e:
            print(f"Error handling new peer: {e}")
    
    def connect_to_peer(self):
        """Connect to a peer manually"""
        peer_ip = self.peer_ip_entry.get().strip()
        peer_port = self.peer_port_entry.get().strip()
        
        if not peer_ip or not peer_port:
            messagebox.showerror("Error", "Please enter peer IP and port")
            return
        
        try:
            peer_port = int(peer_port)
            
            # Create connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((peer_ip, peer_port))
            
            # Send our username
            sock.send(f"HELLO:{self.username}".encode())
            
            # Receive peer's username
            data = sock.recv(1024).decode()
            if data.startswith("HELLO:"):
                peer_username = data.split(':')[1]
                
                # Store peer
                peer_key = f"{peer_username}@{peer_ip}:{peer_port}"
                self.peers[peer_key] = {'socket': sock, 'username': peer_username, 
                                       'addr': (peer_ip, peer_port)}
                
                self.add_message("SYSTEM", f"🤝 Connected to {peer_username} at {peer_ip}:{peer_port}")
                self.update_peers_list()
                
                # Listen for messages
                Thread(target=self.receive_from_peer, args=(peer_key,), daemon=True).start()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {str(e)}")
    
    def receive_from_peer(self, peer_key):
        """Receive messages from a peer"""
        try:
            peer = self.peers[peer_key]
            sock = peer['socket']
            
            while self.listening and peer_key in self.peers:
                data = sock.recv(4096)
                if not data:
                    break
                
                message = data.decode()
                self.add_message("RECEIVED", f"{peer['username']}: {message}")
        
        except Exception as e:
            print(f"Error receiving from {peer_key}: {e}")
        finally:
            # Peer disconnected
            if peer_key in self.peers:
                peer_username = self.peers[peer_key]['username']
                self.add_message("SYSTEM", f"❌ {peer_username} disconnected")
                try:
                    self.peers[peer_key]['socket'].close()
                except:
                    pass
                del self.peers[peer_key]
                self.update_peers_list()
    
    def send_message(self):
        """Send message to all connected peers"""
        message = self.message_entry.get().strip()
        if not message:
            return
        
        if not self.peers:
            messagebox.showwarning("Warning", "No peers connected!")
            return
        
        # Send to all peers
        disconnected = []
        for peer_key, peer in self.peers.items():
            try:
                peer['socket'].send(message.encode())
            except Exception as e:
                print(f"Failed to send to {peer_key}: {e}")
                disconnected.append(peer_key)
        
        # Remove disconnected peers
        for peer_key in disconnected:
            if peer_key in self.peers:
                del self.peers[peer_key]
        
        if disconnected:
            self.update_peers_list()
        
        self.add_message("SENT", f"You: {message}")
        self.message_entry.delete(0, tk.END)
    
    def update_peers_list(self):
        """Update the peers listbox"""
        self.peers_listbox.delete(0, tk.END)
        if not self.peers:
            self.peers_listbox.insert(tk.END, "No peers connected")
        else:
            for peer_key, peer in self.peers.items():
                addr = peer['addr']
                self.peers_listbox.insert(tk.END, f"🟢 {peer['username']} ({addr[0]}:{addr[1]})")
    
    def add_message(self, msg_type, message):
        """Add message to chat display"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        self.chat_display.config(state=tk.NORMAL)
        
        if msg_type == "SENT":
            self.chat_display.insert(tk.END, f"[{timestamp}] {message}\n", "sent")
            self.chat_display.tag_config("sent", foreground="#2980b9", font=("Arial", 10, "bold"))
        elif msg_type == "RECEIVED":
            self.chat_display.insert(tk.END, f"[{timestamp}] {message}\n", "received")
            self.chat_display.tag_config("received", foreground="#27ae60", font=("Arial", 10))
        elif msg_type == "SYSTEM":
            self.chat_display.insert(tk.END, f"[{timestamp}] {message}\n", "system")
            self.chat_display.tag_config("system", foreground="#95a5a6", font=("Arial", 9, "italic"))
        
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def on_closing(self):
        """Clean up on exit"""
        self.listening = False
        
        # Close all peer connections
        for peer in self.peers.values():
            try:
                peer['socket'].close()
            except:
                pass
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = SimplePeerToPeer(root)
    root.mainloop()