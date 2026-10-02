import socket
from threading import Thread
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
BACKLOG = 5
LARGE_MSG_MAGIC = b'\xDE\xAD\xBE\xEF'

# Encryption setup
# IMPORTANT: In production, use secure key exchange (like Diffie-Hellman)
# For this demo, we use a shared secret password
SHARED_PASSWORD = b"MySecretPassword123"  # Change this!

class CryptoHelper:
    """Helper class for encryption/decryption"""
    
    @staticmethod
    def generate_key_from_password(password):
        """Generate encryption key from password"""
        # Use a fixed salt for demo (in production, negotiate salt with client)
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

class EncryptedHybridServer:
    Clients = []
    number = 1
    
    def __init__(self, HOST, TCP_PORT, UDP_PORT, BACKLOG, password):
        # Initialize encryption
        self.cipher = CryptoHelper.create_cipher(password)
        print(f"[Crypto] Encryption initialized with password-based key")
        
        # TCP Socket
        self.tcp_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_srv.bind((HOST, TCP_PORT))
        self.tcp_srv.listen(BACKLOG)
        print(f"[TCP Server] listening on {HOST}:{TCP_PORT} ...")
        
        # UDP Socket
        self.udp_srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_srv.bind((HOST, UDP_PORT))
        print(f"[UDP Server] listening on {HOST}:{UDP_PORT} ...")

    def encrypt_message(self, message):
        """Encrypt a message"""
        if isinstance(message, str):
            message = message.encode()
        encrypted = self.cipher.encrypt(message)
        return encrypted
    
    def decrypt_message(self, encrypted_data):
        """Decrypt a message"""
        try:
            decrypted = self.cipher.decrypt(encrypted_data)
            return decrypted
        except Exception as e:
            print(f"[Crypto] Decryption failed: {e}")
            return None

    def start(self):
        Thread(target=self.listen_tcp, args=(BUFFER_SIZE,), daemon=True).start()
        self.listen_udp()

    def listen_tcp(self, buffer):
        """Handle TCP connections"""
        while True:
            conn, addr = self.tcp_srv.accept()
            print(f"[TCP Server] connected by {addr}")
            
            clientname = EncryptedHybridServer.number
            client = {
                'clientname': EncryptedHybridServer.number,
                'clientsocket': conn,
                'udp_addr': None,
                'last_seen': time.time(),
                'addr': addr
            }
            EncryptedHybridServer.number = EncryptedHybridServer.number + 1
            
            # Send encrypted welcome message
            welcome_msg = f"visitor {clientname} has join"
            self.broadcast_tcp_encrypted(clientname, welcome_msg)
            
            EncryptedHybridServer.Clients.append(client)            
            Thread(target=self.handle_tcp_client, args=(client, buffer)).start()

    def listen_udp(self):
        """Handle UDP packets"""
        print("[UDP Server] Ready to receive UDP packets...")
        while True:
            try:
                data, addr = self.udp_srv.recvfrom(BUFFER_SIZE * 2)  # Encrypted data is larger
                
                # Try to decrypt UDP message
                decrypted = self.decrypt_message(data)
                if not decrypted:
                    continue
                
                message = decrypted.decode(errors='replace').strip()
                parts = message.split(':', 2)
                
                if len(parts) >= 2:
                    try:
                        client_id = int(parts[0])
                        msg_type = parts[1]
                        msg_data = parts[2] if len(parts) > 2 else ''
                        
                        # Update client info
                        for client in EncryptedHybridServer.Clients:
                            if client['clientname'] == client_id:
                                client['udp_addr'] = addr
                                client['last_seen'] = time.time()
                                break
                        
                        if msg_type == 'HEARTBEAT':
                            print(f"[UDP] Heartbeat from client {client_id}")
                        
                        elif msg_type == 'TYPING':
                            print(f"[UDP] Client {client_id} is typing...")
                            self.broadcast_udp_encrypted(client_id, f"TYPING:{client_id}")
                        
                        elif msg_type == 'STOP_TYPING':
                            print(f"[UDP] Client {client_id} stopped typing")
                            self.broadcast_udp_encrypted(client_id, f"STOP_TYPING:{client_id}")
                        
                        elif msg_type == 'PING':
                            encrypted_pong = self.encrypt_message(f"PONG:{int(time.time() * 1000)}")
                            self.udp_srv.sendto(encrypted_pong, addr)
                    
                    except (ValueError, IndexError) as e:
                        print(f"[UDP] Error parsing message: {e}")
            
            except Exception as e:
                print(f"[UDP] Error: {e}")

    def recv_exact(self, conn, num_bytes):
        """Receive exactly num_bytes from socket"""
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
        print(f"[TCP Server] Receiving large encrypted message: {message_length} bytes")
        encrypted_bytes = self.recv_exact(conn, message_length)
        
        # Decrypt the message
        decrypted = self.decrypt_message(encrypted_bytes)
        return decrypted if decrypted else b''

    def send_message_with_length(self, conn, message):
        """Send encrypted message with length prefix"""
        if isinstance(message, str):
            message = message.encode()
        
        # Encrypt first
        encrypted = self.encrypt_message(message)
        message_length = len(encrypted)
        
        # Send with magic header and length
        conn.sendall(LARGE_MSG_MAGIC)
        length_prefix = struct.pack('!I', message_length)
        conn.sendall(length_prefix)
        
        # Send encrypted data in chunks
        sent = 0
        while sent < message_length:
            chunk_size = min(BUFFER_SIZE, message_length - sent)
            chunk = encrypted[sent:sent + chunk_size]
            conn.sendall(chunk)
            sent += chunk_size

    def handle_tcp_client(self, client, BUFFER_SIZE):
        """Handle TCP client with encryption"""
        clientname = client['clientname']
        conn = client['clientsocket']
        
        try:
            while True:
                conn.setblocking(True)
                peek_data = conn.recv(4, socket.MSG_PEEK)
                
                if not peek_data:
                    print(f"[TCP Server] client {clientname} closed the connection.")
                    break
                
                is_large_message = False
                if len(peek_data) >= 4 and peek_data[:4] == LARGE_MSG_MAGIC:
                    is_large_message = True
                    conn.recv(4)  # Consume magic
                
                if is_large_message:
                    decrypted_data = self.receive_message_with_length(conn)
                    if decrypted_data:
                        text = decrypted_data.decode(errors="replace")
                        print(f"[TCP Server] Decrypted Large Message: {text[:100]}...")
                        
                        # Echo back encrypted
                        self.send_message_with_length(conn, decrypted_data)
                        print(f"[TCP Server] Sent encrypted echo")
                else:
                    # Receive encrypted data
                    encrypted_data = conn.recv(BUFFER_SIZE * 2)  # Encrypted is larger
                    if not encrypted_data:
                        print(f"[TCP Server] client {clientname} closed connection.")
                        break
                    
                    # Decrypt
                    decrypted_data = self.decrypt_message(encrypted_data)
                    if not decrypted_data:
                        continue
                    
                    text = decrypted_data.decode(errors="replace")
                    print(f"[TCP Server] Decrypted: {text.strip()}")
                    
                    # Echo back encrypted
                    conn.sendall(encrypted_data)
                    
        except Exception as e:
            print(f"[TCP Server] Error: {e}")
        finally:
            EncryptedHybridServer.Clients.remove(client)
            self.broadcast_tcp_encrypted(clientname, f"visitor {clientname} has left")
            conn.close()

    def broadcast_tcp_encrypted(self, sender, message):
        """Broadcast encrypted TCP message"""
        encrypted = self.encrypt_message(message)
        
        for client in EncryptedHybridServer.Clients:
            clientname = client['clientname']
            conn = client['clientsocket']
            if clientname != sender:
                try:
                    if len(encrypted) > BUFFER_SIZE:
                        self.send_message_with_length(conn, message)
                    else:
                        conn.send(encrypted)
                except Exception as e:
                    print(f"[TCP] Broadcast failed: {e}")

    def broadcast_udp_encrypted(self, sender, message):
        """Broadcast encrypted UDP message"""
        encrypted = self.encrypt_message(message)
        
        for client in EncryptedHybridServer.Clients:
            clientname = client['clientname']
            udp_addr = client['udp_addr']
            if clientname != sender and udp_addr:
                try:
                    self.udp_srv.sendto(encrypted, udp_addr)
                except Exception as e:
                    print(f"[UDP] Broadcast failed: {e}")

if __name__ == '__main__':
    print("="*50)
    print("🔒 ENCRYPTED HYBRID TCP+UDP SERVER")
    print("="*50)
    print(f"Password: {SHARED_PASSWORD.decode()}")
    print("="*50)
    
    server = EncryptedHybridServer(HOST, TCP_PORT, UDP_PORT, BACKLOG, SHARED_PASSWORD)
    server.start()