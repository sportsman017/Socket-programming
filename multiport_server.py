#final
import socket
from threading import Thread
import struct
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

HOST = "127.0.0.1"
BUFFER_SIZE = 256
BACKLOG = 5
LARGE_MSG_MAGIC = b'\xDE\xAD\xBE\xEF'

# Multiple Port Configuration for Different Services
PORT_CONFIG = {
    'general': {
        'tcp_port': 5678,
        'udp_port': 5679,
        'password': b"GeneralPassword123",
        'idle_timeout': 300,  # 5 minutes
        'warning_time': 240,
        'description': 'General Chat Room'
    },
    'gaming': {
        'tcp_port': 5680,
        'udp_port': 5681,
        'password': b"GamingPassword456",
        'idle_timeout': 60,   # 1 minute (strict for games)
        'warning_time': 45,
        'description': 'Gaming Room - Low latency'
    },
    'study': {
        'tcp_port': 5682,
        'udp_port': 5683,
        'password': b"StudyPassword789",
        'idle_timeout': 1800,  # 30 minutes (relaxed for studying)
        'warning_time': 1500,
        'description': 'Study Room - Long sessions allowed'
    },
    'admin': {
        'tcp_port': 5684,
        'udp_port': 5685,
        'password': b"AdminSecurePass000",
        'idle_timeout': 600,   # 10 minutes
        'warning_time': 480,
        'description': 'Admin Room - Secure access'
    }
}

HEARTBEAT_INTERVAL = 3

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

class RoomServer:
    """Individual room server instance"""
    
    def __init__(self, room_name, config):
        self.room_name = room_name
        self.config = config
        self.clients = []
        self.client_number = 1
        
        try:
            # Initialize encryption
            self.cipher = CryptoHelper.create_cipher(config['password'])
            print(f"[{room_name}] Encryption initialized")
            
            # TCP Socket
            self.tcp_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.tcp_srv.bind((HOST, config['tcp_port']))
                self.tcp_srv.listen(BACKLOG)
                print(f"[{room_name}] TCP listening on {HOST}:{config['tcp_port']}")
            except OSError as e:
                print(f"[{room_name}] ERROR: TCP Port {config['tcp_port']} already in use!")
                raise
            
            # UDP Socket
            self.udp_srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.udp_srv.bind((HOST, config['udp_port']))
                print(f"[{room_name}] UDP listening on {HOST}:{config['udp_port']}")
            except OSError as e:
                print(f"[{room_name}] ERROR: UDP Port {config['udp_port']} already in use!")
                self.tcp_srv.close()  # Clean up TCP socket
                raise
            
            # Start timeout monitor
            Thread(target=self.monitor_timeouts, daemon=True).start()
            
        except Exception as e:
            print(f"[{room_name}] Failed to initialize: {e}")
            raise

    def encrypt_message(self, message):
        """Encrypt a message"""
        if isinstance(message, str):
            message = message.encode()
        return self.cipher.encrypt(message)
    
    def decrypt_message(self, encrypted_data):
        """Decrypt a message"""
        try:
            return self.cipher.decrypt(encrypted_data)
        except Exception as e:
            print(f"[{self.room_name}] Decryption failed: {e}")
            return None

    def monitor_timeouts(self):
        """Monitor client timeouts"""
        while True:
            current_time = time.time()
            clients_to_remove = []
            
            for client in self.clients[:]:
                idle_time = current_time - client['last_seen']
                
                # Send warning
                if idle_time >= self.config['warning_time'] and not client.get('warned'):
                    remaining = self.config['idle_timeout'] - int(idle_time)
                    warning_msg = f"⚠️ WARNING: Idle for {int(idle_time)}s. Kicked in {remaining}s!"
                    try:
                        encrypted_warning = self.encrypt_message(warning_msg)
                        client['clientsocket'].send(encrypted_warning)
                        client['warned'] = True
                        print(f"[{self.room_name}] Warning sent to client {client['clientname']}")
                    except Exception as e:
                        print(f"[{self.room_name}] Failed to warn client: {e}")
                
                # Kick if timeout reached
                if idle_time >= self.config['idle_timeout']:
                    print(f"[{self.room_name}] Kicking client {client['clientname']}")
                    clients_to_remove.append(client)
            
            # Remove timed out clients
            for client in clients_to_remove:
                try:
                    kick_msg = f"⏱️ KICKED: Idle timeout ({self.config['idle_timeout']}s)"
                    encrypted_kick = self.encrypt_message(kick_msg)
                    client['clientsocket'].send(encrypted_kick)
                    time.sleep(0.1)
                except:
                    pass
                
                try:
                    client['clientsocket'].close()
                except:
                    pass
                
                if client in self.clients:
                    self.clients.remove(client)
                    self.broadcast_tcp_encrypted(client['clientname'], 
                        f"visitor {client['clientname']} was kicked (idle)")
            
            time.sleep(1)

    def start(self):
        """Start TCP and UDP listeners"""
        Thread(target=self.listen_tcp, daemon=True).start()
        Thread(target=self.listen_udp, daemon=True).start()  # Changed: UDP also in thread

    def listen_tcp(self):
        """Handle TCP connections"""
        while True:
            conn, addr = self.tcp_srv.accept()
            print(f"[{self.room_name}] TCP connected by {addr}")
            
            clientname = self.client_number
            client = {
                'clientname': self.client_number,
                'clientsocket': conn,
                'udp_addr': None,
                'last_seen': time.time(),
                'addr': addr,
                'warned': False
            }
            self.client_number += 1
            
            # Send welcome message
            welcome_msg = f"Welcome to {self.room_name}! visitor {clientname} joined"
            self.broadcast_tcp_encrypted(clientname, welcome_msg)
            
            self.clients.append(client)
            Thread(target=self.handle_tcp_client, args=(client,)).start()

    def listen_udp(self):
        """Handle UDP packets"""
        while True:
            try:
                data, addr = self.udp_srv.recvfrom(BUFFER_SIZE * 2)
                
                decrypted = self.decrypt_message(data)
                if not decrypted:
                    continue
                
                message = decrypted.decode(errors='replace').strip()
                parts = message.split(':', 2)
                
                if len(parts) >= 2:
                    try:
                        client_id = int(parts[0])
                        msg_type = parts[1]
                        
                        # Update client info
                        for client in self.clients:
                            if client['clientname'] == client_id:
                                client['udp_addr'] = addr
                                client['last_seen'] = time.time()
                                client['warned'] = False
                                break
                        
                        if msg_type == 'HEARTBEAT':
                            print(f"[{self.room_name}] Heartbeat from client {client_id}")
                        elif msg_type == 'TYPING':
                            self.broadcast_udp_encrypted(client_id, f"TYPING:{client_id}")
                        elif msg_type == 'STOP_TYPING':
                            self.broadcast_udp_encrypted(client_id, f"STOP_TYPING:{client_id}")
                    
                    except (ValueError, IndexError) as e:
                        print(f"[{self.room_name}] UDP error: {e}")
            
            except Exception as e:
                print(f"[{self.room_name}] UDP error: {e}")

    def recv_exact(self, conn, num_bytes):
        """Receive exactly num_bytes"""
        data = b''
        while len(data) < num_bytes:
            chunk = conn.recv(num_bytes - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data

    def receive_message_with_length(self, conn):
        """Receive encrypted message with length prefix"""
        length_bytes = self.recv_exact(conn, 4)
        message_length = struct.unpack('!I', length_bytes)[0]
        encrypted_bytes = self.recv_exact(conn, message_length)
        decrypted = self.decrypt_message(encrypted_bytes)
        return decrypted if decrypted else b''

    def send_message_with_length(self, conn, message):
        """Send encrypted message with length prefix"""
        if isinstance(message, str):
            message = message.encode()
        
        encrypted = self.encrypt_message(message)
        message_length = len(encrypted)
        
        conn.sendall(LARGE_MSG_MAGIC)
        length_prefix = struct.pack('!I', message_length)
        conn.sendall(length_prefix)
        
        sent = 0
        while sent < message_length:
            chunk_size = min(BUFFER_SIZE, message_length - sent)
            chunk = encrypted[sent:sent + chunk_size]
            conn.sendall(chunk)
            sent += chunk_size

    def handle_tcp_client(self, client):
        """Handle TCP client"""
        clientname = client['clientname']
        conn = client['clientsocket']
        
        try:
            while True:
                conn.setblocking(True)
                peek_data = conn.recv(4, socket.MSG_PEEK)
                
                if not peek_data:
                    print(f"[{self.room_name}] Client {clientname} closed connection")
                    break
                
                is_large_message = False
                if len(peek_data) >= 4 and peek_data[:4] == LARGE_MSG_MAGIC:
                    is_large_message = True
                    conn.recv(4)
                
                if is_large_message:
                    decrypted_data = self.receive_message_with_length(conn)
                    if decrypted_data:
                        text = decrypted_data.decode(errors="replace")
                        print(f"[{self.room_name}] Large message: {text[:100]}...")
                        
                        client['last_seen'] = time.time()
                        client['warned'] = False
                        
                        self.send_message_with_length(conn, decrypted_data)
                else:
                    encrypted_data = conn.recv(BUFFER_SIZE * 2)
                    if not encrypted_data:
                        break
                    
                    decrypted_data = self.decrypt_message(encrypted_data)
                    if not decrypted_data:
                        continue
                    
                    text = decrypted_data.decode(errors="replace")
                    print(f"[{self.room_name}] Message: {text.strip()}")
                    
                    client['last_seen'] = time.time()
                    client['warned'] = False
                    
                    conn.sendall(encrypted_data)
                    
        except Exception as e:
            print(f"[{self.room_name}] Error: {e}")
        finally:
            if client in self.clients:
                self.clients.remove(client)
                self.broadcast_tcp_encrypted(clientname, f"visitor {clientname} left")
            try:
                conn.close()
            except:
                pass

    def broadcast_tcp_encrypted(self, sender, message):
        """Broadcast encrypted TCP message"""
        encrypted = self.encrypt_message(message)
        
        for client in self.clients:
            if client['clientname'] != sender:
                try:
                    if len(encrypted) > BUFFER_SIZE:
                        self.send_message_with_length(client['clientsocket'], message)
                    else:
                        client['clientsocket'].send(encrypted)
                except Exception as e:
                    print(f"[{self.room_name}] Broadcast failed: {e}")

    def broadcast_udp_encrypted(self, sender, message):
        """Broadcast encrypted UDP message"""
        encrypted = self.encrypt_message(message)
        
        for client in self.clients:
            if client['clientname'] != sender and client['udp_addr']:
                try:
                    self.udp_srv.sendto(encrypted, client['udp_addr'])
                except Exception as e:
                    print(f"[{self.room_name}] UDP broadcast failed: {e}")

class MultiPortServer:
    """Main server managing multiple room servers"""
    
    def __init__(self):
        self.rooms = {}
        
    def start_all_rooms(self):
        """Start all configured rooms"""
        print("="*60)
        print("🌐 MULTI-PORT CHAT SERVER")
        print("="*60)
        
        failed_rooms = []
        
        for room_name, config in PORT_CONFIG.items():
            print(f"\n📡 Starting Room: {room_name.upper()}")
            print(f"   Description: {config['description']}")
            print(f"   TCP Port: {config['tcp_port']}")
            print(f"   UDP Port: {config['udp_port']}")
            print(f"   Password: {config['password'].decode()}")
            print(f"   Idle Timeout: {config['idle_timeout']}s")
            
            try:
                room_server = RoomServer(room_name, config)
                room_server.start()
                self.rooms[room_name] = room_server
                print(f"   ✅ {room_name} started successfully!")
            except Exception as e:
                print(f"   ❌ {room_name} failed to start: {e}")
                failed_rooms.append(room_name)
        
        print("\n" + "="*60)
        if failed_rooms:
            print(f"⚠️  Some rooms failed to start: {', '.join(failed_rooms)}")
            print(f"✅ {len(self.rooms)} rooms started successfully")
            print("\n💡 TIP: Check if ports are already in use:")
            print("   Windows: netstat -ano | findstr :PORT")
            print("   Linux/Mac: lsof -i :PORT")
        else:
            print("✅ All rooms started successfully!")
        print("="*60)
        
        if not self.rooms:
            print("\n❌ ERROR: No rooms could be started!")
            print("Server cannot run without any active rooms.")
            return
        
        # Keep main thread alive
        print("\n🔄 Server running... Press Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down server...")
            print("Goodbye!")

if __name__ == '__main__':
    server = MultiPortServer()
    server.start_all_rooms()