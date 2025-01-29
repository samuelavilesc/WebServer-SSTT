# coding=utf-8
#!/usr/bin/env python3

import socket
import selectors    #https://docs.python.org/3/library/selectors.html
import select
import types        # Para definir el tipo de datos data
import argparse     # Leer parametros de ejecución
import os           # Obtener ruta y extension
from datetime import datetime, timedelta # Fechas de los mensajes HTTP
import time         # Timeout conexión
import sys          # sys.exit
import re           # Analizador sintáctico
import logging      # Para imprimir logs


RE_HTTP=re.compile(r"HTTP\/1\.1")
RE_URL_PARAMETERS=re.compile(r"\?.* ")
RE_RECURSO=re.compile(r"GET \/.* ")
RE_HEADERS=re.compile(r"\\r\\n.*\\r\\n\\r\\n")
BUFSIZE = 8192 # Tamaño máximo del buffer que se puede utilizar
TIMEOUT_CONNECTION = 20 # Timout para la conexión persistente
MAX_ACCESOS = 10
BACK_LOG = 64
# Extensiones admitidas (extension, name in HTTP)
filetypes = {"gif":"image/gif", "jpg":"image/jpg", "jpeg":"image/jpeg", "png":"image/png", "htm":"text/htm", 
             "html":"text/html", "css":"text/css", "js":"text/js"}

# Configuración de logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s.%(msecs)03d] [%(levelname)-7s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()

headers_map={}
actual_cookie=0

def enviar_mensaje(cs, data):
    """ Esta función envía datos (data) a través del socket cs
        Devuelve el número de bytes enviados.
    """
    return cs.send(data)


def recibir_mensaje(cs):
    """ Esta función recibe datos a través del socket cs
        Leemos la información que nos llega. recv() devuelve un string con los datos.
    """
    return cs.recv(BUFSIZE).decode()


def cerrar_conexion(cs):
    """ Esta función cierra una conexión activa.
    """
    cs.close()


def process_cookies(headers,  cs):
    """ Esta función procesa la cookie cookie_counter
        1. Se analizan las cabeceras en headers para buscar la cabecera Cookie
        2. Una vez encontrada una cabecera Cookie se comprueba si el valor es cookie_counter
        3. Si no se encuentra cookie_counter , se devuelve 1
        4. Si se encuentra y tiene el valor MAX_ACCESSOS se devuelve MAX_ACCESOS
        5. Si se encuentra y tiene un valor 1 <= x < MAX_ACCESOS se incrementa en 1 y se devuelve el valor
    """
    pass
def send_file(cs,file,size):
    file_open=open(file,"rb")
    data=file_open.read(BUFSIZE)
    sended=0
    while sended<size:

        sended+=cs.send(data)
        data=file_open.read(BUFSIZE)

    file_open.close()


def send_response(msg,cs):
    global actual_cookie
    isOK=False
    if msg=="405":
        resp="405 Method Not Allowed\r\n"
        file="405.html"
    elif msg=="505":

        resp="505 HTTP Version Not Supported\r\n"
        file="505.html"
    else:
        isOK=True
        resp="200 OK\r\n"
        file=str(msg)
    
    size=os.stat(file).st_size
    
    if isOK:
        file_type = filetypes[msg[1:].split(".")[1]]
        resp="HTTP/1.1 "+resp+"Conte/nt-Type:"+file_type+"\r\n"+"Content-Length: "+str(size)+"\r\n"+"Date:"+datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')+"\r\n"+"Server: foropatinetes_8656.org\r\n"+ "Connection: Keep-Alive\r\n"+"Keep-Alive: timeout="+str(TIMEOUT_CONNECTION)+ ", max=5\r\n"+"Set-cookie: cookie_counter="+str(actual_cookie)+" ;Max-Age=25"+"\r\n"+"\r\n"
    else:
        resp="HTTP/1.1 "+resp+"Content-Type:"+" text/html"+"\r\n"+"Content-Length: "+str(size)+"\r\n"+"Date:"+datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')+"\r\n"+ "Connection: Keep-Alive\r\n"+"Keep-Alive: timeout="+str(TIMEOUT_CONNECTION)+ ", max=5\r\n"+"\r\n"
    enviar_mensaje(cs,resp.encode())
    send_file(cs,file,size)
def process_web_request(cs, webroot):

    while True:
        #recibir datos con select
        rsublist, wsublist, xsublist=select.select([cs],[], [],TIMEOUT_CONNECTION)
        #comprobar si hay que cerrar la conexion por timeout
        if rsublist:
            msg = recibir_mensaje(cs)
            if not re.findall(RE_HTTP,msg): # sino encuentra http 1.1 error
                ##error no está bien formateada según HTTP 1.1 devolvemos 505
                send_response("505", cs)
                continue
            elif re.match(RE_POST, msg): #si es post lo procesamos
                process_post_request(cs,msg)
                continue
            elif not re.findall(RE_GET,msg) :# si no encontramos get error
                send_file("405",cs)
                continue
            if re.findall(RE_URL_PARAMETERS,msg):
                msg=re.sub(RE_URL_PARAMETERS," ",msg)
            recurso = re.findall(RE_RECURSO, msg)
            if recurso:
                recurso = recurso[0].replace("GET", "").replace(" ", "").replace("HTTP", "")
                # Si el recurso es la raíz, asignamos "index.html"
                recurso = webroot + ("index.html" if recurso == "/" else recurso.lstrip("/"))
            headers=re.findall(RE_HEADERS,repr(msg))
            if not os.path.isfile(recurso):
                    send_file("404",cs)
            elif headers:
                headers_map=process_headers(headers[0],cs)
                ret_cookies=process_cookies(headers[0],cs)
                        
                if ret_cookies==MAX_ACCESOS: # desconectar del servidor + send error
                    send_file("403", cs)
                    logging.info("LImite de accesos")

                        
                        
                    return 

                    else:#TODO añadir set cookies del valor

                        actual_cookie=ret_cookies+1
                        size=os.stat(recurso).st_size
                        file_type=os.path.basename(recurso).split(".")[1]
                                        
                        send_file(recurso, cs)
                


        else:
            #timeout alcanzado
            msg="Error: timeout alcanzado\n"
            enviar_mensaje(cs,msg)

    """ Procesamiento principal de los mensajes recibidos.
        Típicamente se seguirá un procedimiento similar al siguiente (aunque el alumno puede modificarlo si lo desea)

        * Bucle para esperar hasta que lleguen datos en la red a través del socket cs con select()

            * Se comprueba si hay que cerrar la conexión por exceder TIMEOUT_CONNECTION segundos
              sin recibir ningún mensaje o hay datos. Se utiliza select.select

            * Si no es por timeout y hay datos en el socket cs.
                * Leer los datos con recv.
                * Analizar que la línea de solicitud y comprobar está bien formateada según HTTP 1.1
                    * Devuelve una lista con los atributos de las cabeceras.
                    * Comprobar si la versión de HTTP es 1.1
                    * Comprobar si es un método GET o POST. Si no devolver un error Error 405 "Method Not Allowed".
                    * Leer URL y eliminar parámetros si los hubiera
                    * Comprobar si el recurso solicitado es /, En ese caso el recurso es index.html
                    * Construir la ruta absoluta del recurso (webroot + recurso solicitado)
                    * Comprobar que el recurso (fichero) existe, si no devolver Error 404 "Not found"
                    * Analizar las cabeceras. Imprimir cada cabecera y su valor. Si la cabecera es Cookie comprobar
                      el valor de cookie_counter para ver si ha llegado a MAX_ACCESOS.
                      Si se ha llegado a MAX_ACCESOS devolver un Error "403 Forbidden"
                    * Obtener el tamaño del recurso en bytes.
                    * Extraer extensión para obtener el tipo de archivo. Necesario para la cabecera Content-Type
                    * Preparar respuesta con código 200. Construir una respuesta que incluya: la línea de respuesta y
                      las cabeceras Date, Server, Connection, Set-Cookie (para la cookie cookie_counter),
                      Content-Length y Content-Type.
                    * Leer y enviar el contenido del fichero a retornar en el cuerpo de la respuesta.
                    * Se abre el fichero en modo lectura y modo binario
                        * Se lee el fichero en bloques de BUFSIZE bytes (8KB)
                        * Cuando ya no hay más información para leer, se corta el bucle

            * Si es por timeout, se cierra el socket tras el período de persistencia.
                * NOTA: Si hay algún error, enviar una respuesta de error con una pequeña página HTML que informe del error.
    """


def main():
    """ Función principal del servidor
    """

    try:

        # Argument parser para obtener la ip y puerto de los parámetros de ejecución del programa. IP por defecto 0.0.0.0
        parser = argparse.ArgumentParser()
        parser.add_argument("-p", "--port", help="Puerto del servidor", type=int, required=True)
        parser.add_argument("-ip", "--host", help="Dirección IP del servidor o localhost", required=True)
        parser.add_argument("-wb", "--webroot", help="Directorio base desde donde se sirven los ficheros (p.ej. /home/user/mi_web)")
        parser.add_argument('--verbose', '-v', action='store_true', help='Incluir mensajes de depuración en la salida')
        args = parser.parse_args()


        if args.verbose:
            logger.setLevel(logging.DEBUG)

        logger.info('Enabling server in address {} and port {}.'.format(args.host, args.port))

        logger.info("Serving files from {}".format(args.webroot))

        #Creación socket TCP
        parent_socket=socket.socket(family=socket.AF_INET,type=socket.SOCK_STREAM, proto=0)
        #Permitir reusar la direccion vinculada a otro proceso
        parent_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if parent_socket.bind((args.host,args.port)) == -1:
            sys.exit("Error haciendo el bind()")

        parent_socket.listen(BACK_LOG)
        while True:
            #aceptamos la conexion
            socket_hijo,addr=parent_socket.accept()
            #creamos proceso hijo
            pid=os.fork()
            if pid == 0:
                #soy proceso hijo cierro socket del padre trabajo con el nuevo
                parent_socket.close()
                process_web_request(socket_hijo,args.webroot)
                sys.exit()
            else:
                #soy proceso padre cierro el socket que gestiona el hijo
                socket_hijo.close()

        """ Funcionalidad a realizar
        * Crea un socket TCP (SOCK_STREAM)
        * Permite reusar la misma dirección previamente vinculada a otro proceso. Debe ir antes de sock.bind
        * Vinculamos el socket a una IP y puerto elegidos

        * Escucha conexiones entrantes

        * Bucle infinito para mantener el servidor activo indefinidamente
            - Aceptamos la conexión

            - Creamos un proceso hijo

            - Si es el proceso hijo se cierra el socket del padre y procesar la petición con process_web_request()

            - Si es el proceso padre cerrar el socket que gestiona el hijo.
        """
    except KeyboardInterrupt:
        True

if __name__== "__main__":
    main()
