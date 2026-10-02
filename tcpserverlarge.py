import socket
from threading import Thread
import struct

HOST = "127.0.0.1"
PORT = 5678
BUFFER_SIZE = 1
BACKLOG = 5
LARGE_MSG_MAGIC = b'\xDE\xAD\xBE\xEF'  # Magic bytes to identify large messages

class server:
    Clients = []
    number = 1

    def __init__(self, HOST, PORT, BACKLOG):
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind((HOST, PORT))
        self.srv.listen(BACKLOG)
        print(f"[server] listening on {HOST}:{PORT} ...")

    def listen(self, buffer):
        while True:
            conn, addr = self.srv.accept()
            print(f"[server] connected by {addr}")
            
            clientname = server.number
            client = {'clientname': server.number, 'clientsocket': conn}
            server.number = server.number + 1
            self.broadcast_message(clientname, "visitor " + str(clientname) + " has join")
            server.Clients.append(client)            
            Thread(target=self.handle_new_client, args=(client, buffer)).start()

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
        """Receive message with length prefix"""
        # Receive 4-byte length prefix
        length_bytes = self.recv_exact(conn, 4)
        message_length = struct.unpack('!I', length_bytes)[0]
        
        print(f"[server] Receiving large message: {message_length} bytes")
        
        # Receive the full message in chunks
        message_bytes = self.recv_exact(conn, message_length)
        return message_bytes

    def send_message_with_length(self, conn, message):
        """Send message with length prefix"""
        if isinstance(message, str):
            message_bytes = message.encode()
        else:
            message_bytes = message
            
        message_length = len(message_bytes)
        
        # Send 4-byte length prefix
        length_prefix = struct.pack('!I', message_length)
        conn.sendall(length_prefix)
        
        # Send message in chunks
        sent = 0
        while sent < message_length:
            chunk_size = min(BUFFER_SIZE, message_length - sent)
            chunk = message_bytes[sent:sent + chunk_size]
            conn.sendall(chunk)
            sent += chunk_size

    def handle_new_client(self, client, BUFFER_SIZE):
        clientname = client['clientname']
        conn = client['clientsocket']
        try:
            while True:
                # Peek at the first few bytes to determine message type
                # Always peek at least 4 bytes to check for length prefix
                conn.setblocking(True)
                peek_data = conn.recv(max(4, BUFFER_SIZE), socket.MSG_PEEK)
                
                if not peek_data:
                    print("[server] client closed the connection.")
                    break
                
                # Check if this is a length-prefixed message
                is_large_message = False
                if len(peek_data) >= 4:
                    try:
                        potential_length = struct.unpack('!I', peek_data[:4])[0]
                        # Heuristic: if length > BUFFER_SIZE and < 1MB, treat as length prefix
                        if BUFFER_SIZE < potential_length < 1000000:
                            is_large_message = True
                    except:
                        pass
                
                if is_large_message:
                    # Receive large message with length prefix
                    data = self.receive_message_with_length(conn)
                    text = data.decode(errors="replace")
                    print(f"[server] Read Large Message ({len(data)} bytes): {text[:100]}...")
                    print(f"[server] Echoing back large message...")
                    
                    # Echo back with length prefix
                    self.send_message_with_length(conn, data)
                    print(f"[server] Sent Large Message ({len(data)} bytes)")
                else:
                    # Normal small message
                    data = conn.recv(BUFFER_SIZE)
                    
                    if not data:
                        print("[server] client closed the connection.")
                        break
                    
                    text = data.decode(errors="replace")
                    print(f"Read Message: {text}", end="")
                    print(f"Send Message: {text.strip()}")
                    
                    # Echo back normally
                    conn.sendall(data)
                    
        except Exception as e:
            print(f"[server] Error handling client {clientname}: {e}")
        finally:
            server.Clients.remove(client)
            self.broadcast_message(clientname, "visitor " + str(clientname) + " has left")
            conn.close()
            if len(server.Clients) == 0:
                self.srv.close()
                print("[server] socket closed.")

    def broadcast_message(self, sender, message):
        """Broadcast message to all clients except sender"""
        for client in self.Clients:
            clientname = client['clientname']
            conn = client['clientsocket']
            if clientname != sender:
                try:
                    message_bytes = message.encode()
                    # Use length prefix if message is large
                    if len(message_bytes) > BUFFER_SIZE:
                        self.send_message_with_length(conn, message_bytes)
                    else:
                        conn.send(message_bytes)
                except Exception as e:
                    print(f"[server] Failed to broadcast to client {clientname}: {e}")

if __name__ == '__main__':
    Server = server(HOST, PORT, BACKLOG)
    Server.listen(BUFFER_SIZE)