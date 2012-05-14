#!/usr/bin/env python

import re
import hashlib, base64
import SocketServer, threading, time


# Constants---------------------------------------------------------------------
__version__ = 0.1
recv_size   = 4096


# Binary Helpers ---------------------------------------------------------------

def ByteToHex( byteStr ):
    """
    Convert a byte string to it's hex string representation e.g. for output.
    """
    return ''.join( [ "%02X " % ord( x ) for x in byteStr ] ).strip()

def get_bit(number, bit):
    """
    The bit patern for the number 4 is '00000100'
    The third bit is True
    
    >>> get_bit(4,1)
    False
    >>> get_bit(4,2)
    False
    >>> get_bit(4,3)
    True
    >>> get_bit(4,4)
    False
    """
    return number &  pow(2,bit-1) != 0


# WebSocket --------------------------------------------------------------------

OPCODE_CONTINUATION =  0
OPCODE_TEXT         =  1
OPCODE_BINARY       =  2
OPCODE_CLOSE        =  8
OPCODE_PING         =  9
OPCODE_PONG         = 10

websocket_handshake = """HTTP/1.1 101 Switching Protocols\r
Upgrade: websocket\r
Connection: Upgrade\r
Sec-WebSocket-Accept: %(websocket_accept)s\r\n\r\n"""

def websocket_frame_decode(data):
    """
    http://tools.ietf.org/html/rfc6455#section-5.2
    """

    # Convert data to python 'int's to use bitwise operators
    data = [ord(i) for i in data]
    
    # Extract control bits
    fin            = get_bit(data[0], 8)
    opcode         = data[0] % pow(2,4)
    masked         = get_bit(data[1], 8)
    payload_length = data[1] % pow(2,7)
    #print ("fin:%s opcode:%s masked:%s payload_length:%s" % (fin, opcode, masked, payload_length))
    
    if not fin:
        raise Exception('unsuported fragmented frames')
    
    # Payload Length
    data_start_point = 2
    if   payload_length == 126:
        extended_payload_length = 2
        data_start_point += extended_payload_length
        raise Exception('unsuported payload length')
    elif payload_length == 127:
        extended_payload_length = 8
        data_start_point += extended_payload_length
        raise Exception('unsuported payload length')
    
    # Mask
    masking_key = [0,0,0,0]
    if masked:
        masking_key = data[data_start_point:data_start_point+4]
        data_start_point += 4
    
    # Convert payload_data to python type
    data_convert_function = chr #lambda i: i # AllanC - close frames can have data in, int's cant be concatinated with b''.join ... humm
    if opcode == OPCODE_TEXT:
        data_convert_function = chr
    if opcode == OPCODE_BINARY:
        #raise Exception('untested binary characters')
        pass
    
    payload_data = b''.join([data_convert_function(item^masking_key[index%4]) for index, item in enumerate(data[data_start_point:])])
    
    return payload_data, opcode


def websocket_frame_encode(data, opcode=OPCODE_TEXT, fin=True, masked=False):
    if not fin:
        raise Exception('unsuported fragmented frames')
    
    # Create control byte
    control = int(fin) << 7 | opcode #'\x81'
    
    # Create payload_length and extended_payload_length bytes
    payload_length = len(data)
    if payload_length > 65535:
        payload_length = 127
        raise Exception('unsuported payload length')
    elif payload_length > 125:
        payload_length = 126
        raise Exception('unsuported payload length')
    payload_length = int(masked) << 7 | payload_length 
    
    # Create mask bytes
    if masked:
        raise Exception('unsuported masked')
    
    return chr(control) + chr(payload_length) + data


# Connection Handlers ----------------------------------------------------------

clients = {'websocket':[],'tcp':[],'udp':[]}

def clients_send(data):
    """
    Send the data to all known clients
    """
    
    print(data)
    
    def send(client, data):
        try   : client.request.send(data)
        except: print('error echoing to client')
    
    websocket_data_frame = websocket_frame_encode(data)
    for websocket_client in clients['websocket']:
        send(websocket_client, websocket_data_frame)
        
    for tcp_client in clients['tcp']:
        send(tcp_client, data)
    
    for udp_client in clients['udp']:
        pass
    


class WebSocketEchoRequestHandler(SocketServer.BaseRequestHandler):
    def setup(self):
        print self.client_address, 'connected!'
        websocket_request = self.request.recv(recv_size)
        websocket_key     = re.search(r'Sec-WebSocket-Key:\s?(.*)', websocket_request).group(1).strip()
        websocket_accept  = base64.b64encode(hashlib.sha1('%s%s' % (websocket_key ,'258EAFA5-E914-47DA-95CA-C5AB0DC85B11')).digest())
        self.request.send(websocket_handshake % {'websocket_accept':websocket_accept})
        clients['websocket'].append(self)
    
    def handle(self):
        while True:
            data_recv = self.request.recv(recv_size)
            
            data, opcode = websocket_frame_decode(data_recv)
            if opcode == OPCODE_TEXT:
                clients_send(data)
            elif opcode == OPCODE_CLOSE:
                self.request.send(websocket_frame_encode(data, opcode=OPCODE_CLOSE))
                break
            elif opcode == OPCODE_PING:
                self.request.send(websocket_frame_encode(data, opcode=OPCODE_PONG ))
            
            time.sleep(0)

    def finish(self):
        print self.client_address, 'disconnected!'
        clients['websocket'].remove(self)


class TCPEchoRequestHandler(SocketServer.BaseRequestHandler):
    def setup(self):
        print self.client_address, 'connected!'
        clients['tcp'].append(self)
    
    def handle(self):
        while True:
            data = self.request.recv(recv_size)
            
            if data:
                clients_send(data)
                if data.strip() == 'exit':
                    break
            
            time.sleep(0)
    
    def finish(self):
        print self.client_address, 'disconnected!'
        #self.request.send('bye ' + str(self.client_address) + '\n')
        clients['tcp'].remove(self)


class UDPEchoRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        # TODO - clients need to register with the UDP handler
        data = self.request[0].strip()
        socket = self.request[1]
        print("{} wrote:".format(self.client_address[0]))
        print(data)
        socket.sendto(data.upper(), self.client_address)



# Threaded Servers -------------------------------------------------------------

servers = []
def start_server(server):
    server_thread = threading.Thread(target=server.serve_forever) 
    server_thread.daemon = True # Exit the server thread when the main thread terminates
    server_thread.start() # Start a thread with the server -- that thread will then start one more thread for each request
    servers.append(server)
    #print("Server loop running in thread:", server_thread.name)

def stop_servers():
    for server in servers:
        server.shutdown()

# Command Line Arguments -------------------------------------------------------

def get_args():
    import argparse
    parser = argparse.ArgumentParser(
        description = """Lightweight Echo server for UDP, TCP and WebSockets""",
        epilog      = """@calaldees"""
    )
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('-s','--serve', nargs='+', choices=['udp', 'tcp', 'websocket'], metavar='SERVER_TYPE', default=['udp','tcp','websocket'])
    parser.add_argument('-u','--udp_port'      , type=int, help='UDP port'      , default=9871)
    parser.add_argument('-t','--tcp_port'      , type=int, help='TCP port'      , default=9872)
    parser.add_argument('-w','--websocket_port', type=int, help='WebSocket port', default=9873)
    return parser.parse_args()

# Main -------------------------------------------------------------------------

if __name__ == "__main__":
    args = get_args()
    for server_type in args.serve:
        if server_type=='websocket':
            start_server(SocketServer.ThreadingTCPServer(('', args.websocket_port), WebSocketEchoRequestHandler))
        if server_type=='tcp':
            start_server(SocketServer.ThreadingTCPServer(('', args.tcp_port      ), TCPEchoRequestHandler      ))
        if server_type=='udp':
            start_server(SocketServer.UDPServer         (('', args.udp_port      ), UDPEchoRequestHandler      ))

    while True:
        time.sleep(10)

#-------------------------------------------------------------------------------
# Working
#-------------------------------------------------------------------------------

"""

import time

# Handle Connection
def connection(client):
    websocket_request = client.recv(4096)
    websocket_key     = re.search(r'Sec-WebSocket-Key:\s?(.*)', websocket_request).group(1).strip()
    websocket_accept  = base64.b64encode(hashlib.sha1('%s%s' % (websocket_key ,'258EAFA5-E914-47DA-95CA-C5AB0DC85B11')).digest())
    client.send(handshake % {'websocket_accept':websocket_accept})
    
    while True:
        data_recv = client.recv(4096)
        
        data, opcode = decode_frame(data_recv)
        if opcode == OPCODE_TEXT:
            #msg_send.append(data)
            print(data)
            client.send(encode_frame(data))
        elif opcode == OPCODE_CLOSE:
            break
        elif opcode == OPCODE_PING:
            client.send(encode_frame('pong', opcode=OPCODE_PONG))
        
        time.sleep(0)
    
    client.close()

# Setup Server Socket

import socket, threading
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('', port))
sock.listen(5)

print "TCPServer Waiting for clients on port %d" % port
while True:
    client, address = sock.accept()
    threading.Thread(target=connection, args=(client,)).start()
"""
#server = SocketServer.ThreadingTCPServer(('', port), WebSocketEchoRequestHandler)
#server.serve_forever()
