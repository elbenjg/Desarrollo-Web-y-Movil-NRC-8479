import argparse
import json
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import stomp

DESTINO = "/queue/pedidos"

def interpretar(cuerpo: str, headers: dict):
    formato = headers.get("x-formato", "").lower()
    tipo_mime = headers.get("content-type", "").lower()
    if not formato:
        if "application/json" in tipo_mime:
            formato = "json"
        elif "application/xml" in tipo_mime or "text/xml" in tipo_mime:
            formato = "xml"
        else:
            formato = "texto"
    if formato == "texto":
        return formato, cuerpo
    if formato == "fijo":
        if len(cuerpo) != 36:
            raise ValueError(f"Registro de ancho fijo inválido: {len(cuerpo)} se espera 36")
        identificador = cuerpo[0:6]
        cliente = cuerpo[6:26].rstrip()
        monto = cuerpo[26:36]
        if not (identificador.isascii() and identificador.isdigit() and len(monto) == 10 and monto[:7].isdigit() and monto[7] == "." and monto[8:].isdigit()):
            raise ValueError("Campos numéricos de ancho fijo inválidos")
        return formato, {"id": identificador, "cliente": cliente, "monto": monto}
    if formato == "json":
        return formato, json.loads(cuerpo)
    if formato == "xml":
        raiz = ET.fromstring(cuerpo)
        if raiz.tag != "pedido":
            raise ValueError("El nodo raíz de XML debe ser <pedido>")    
        return formato, {elemento.tag: elemento.text for elemento in raiz}
    raise ValueError(f"Formato no soportado: {formato}")

class EscuchadorAsincrono(stomp.ConnectionListener):
    def __init__(self, conexion: stomp.Connection12, pool: ThreadPoolExecutor):
        self.conexion = conexion
        self.pool = pool

    def on_error(self, frame):
        print(f"ERROR del broker: {frame.body}")

    def on_disconnected(self):
        print("Conexión STOMP cerrada")

    def on_message(self, frame):
        ack_id = frame.headers["ack"]
        body = frame.body
        headers = frame.headers
        # Despacho asíncrono inmediato al pool de hilos sin bloquear la recepción STOMP
        self.pool.submit(self._procesar_mensaje_async, body, headers, ack_id)

    def _procesar_mensaje_async(self, cuerpo: str, headers: dict, ack_id: str):
        try:
            formato, contenido = interpretar(cuerpo, headers)
            print(f"\n[PROCESADO ASÍNCRONO] formato={formato}")
            if isinstance(contenido, str):
                print(contenido)
            else:
                print(json.dumps(contenido, ensure_ascii=False, indent=2))
            # Reconocimiento al broker tras completar el trabajo
            self.conexion.ack(id=ack_id)
        except Exception as exc:
            print(f"[MENSAJE NO VÁLIDO] {exc}")
            self.conexion.nack(id=ack_id, requeue="false")

def main():
    parser = argparse.ArgumentParser(description="Consumidor Asíncrono STOMP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=61613)
    parser.add_argument("--usuario", default="demo")
    parser.add_argument("--clave", default="demo123")
    parser.add_argument("--workers", type=int, default=5, help="Número de hilos de procesamiento asíncrono")
    args = parser.parse_args()

    executor = ThreadPoolExecutor(max_workers=args.workers)
    conexion = stomp.Connection12([(args.host, args.port)], vhost="/")
    conexion.set_listener("pedidos", EscuchadorAsincrono(conexion, executor))

    try: 
        conexion.connect(args.usuario, args.clave, wait=True)
        # Se escala prefetch-count a la cantidad de hilos disponibles
        conexion.subscribe(
            destination=DESTINO,
            id="lector-pedidos-async",
            ack="client-individual",
            headers={"prefetch-count": str(args.workers)}
        )
        print(f"Escuchando asincrónicamente en {DESTINO} con {args.workers} trabajadores.")
        while conexion.is_connected():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nDeteniendo consumidor asíncrono...")
    finally:
        executor.shutdown(wait=False)
        if conexion.is_connected():
            conexion.disconnect()

if __name__ == "__main__":
    main()
