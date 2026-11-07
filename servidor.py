"""
PFO 3: Rediseño del PFO 2 como sistema distribuido.
Servidor con sockets TCP + cola + pool de workers + SQLite.

El servidor recibe tareas por socket, las encola y los workers
(threads con su pool) las procesan usando la lógica del PFO 2:
registro, login y listado de usuarios.
"""
import socket
import threading
import queue
import json
import uuid
import time
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

HOST = "0.0.0.0"
PORT = 5000
MAX_WORKERS = 4
DB = "usuarios.db"

# ----- Cola de mensajes (simula RabbitMQ) -----
cola_tareas = queue.Queue()
resultados = {}
lock_resultados = threading.Lock()

# ----- Base de datos (la misma del PFO 2) -----
def inicializar_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        conn.commit()

def registrar_usuario(usuario, password):
    try:
        with sqlite3.connect(DB) as conn:
            conn.execute(
                "INSERT INTO usuarios (usuario, password_hash) VALUES (?, ?)",
                (usuario, generate_password_hash(password)),
            )
            conn.commit()
        return {"codigo": 201, "mensaje": f"Usuario '{usuario}' registrado correctamente."}
    except sqlite3.IntegrityError:
        return {"codigo": 409, "mensaje": f"El usuario '{usuario}' ya existe."}

def login(usuario, password):
    with sqlite3.connect(DB) as conn:
        fila = conn.execute(
            "SELECT password_hash FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()
    if fila and check_password_hash(fila[0], password):
        return {"codigo": 200, "mensaje": f"Login exitoso. Bienvenido/a {usuario}."}
    return {"codigo": 401, "mensaje": "Credenciales incorrectas."}

def listar_usuarios():
    with sqlite3.connect(DB) as conn:
        filas = conn.execute("SELECT usuario FROM usuarios ORDER BY id").fetchall()
    return {"codigo": 200, "usuarios": [f[0] for f in filas]}

# ----- Lógica de negocio (heredada del PFO 2) -----
def procesar_tarea(payload):
    accion = payload.get("accion")
    if accion == "registro":
        return registrar_usuario(payload["usuario"], payload["password"])
    if accion == "login":
        return login(payload["usuario"], payload["password"])
    if accion == "listar":
        return listar_usuarios()
    return {"codigo": 400, "mensaje": f"Acción desconocida: {accion}"}

# ----- Worker: consume de la cola y procesa -----
def worker_loop(worker_id):
    print(f"[{worker_id}] Iniciado y listo para recibir tareas.")
    while True:
        task_id, payload = cola_tareas.get()
        inicio = time.time()
        try:
            resultado = procesar_tarea(payload)
        except Exception as e:
            resultado = {"codigo": 500, "mensaje": f"Error interno: {e}"}
        resultado["worker"] = worker_id
        resultado["ms"] = round((time.time() - inicio) * 1000, 1)
        with lock_resultados:
            resultados[task_id] = resultado
        print(f"[{worker_id}] Tarea {task_id} ({payload.get('accion')}) lista en {resultado['ms']} ms")

# ----- Servidor de entrada: recibe por socket y encola -----
def manejar_cliente(conn, addr):
    print(f"[+] Conexión desde {addr}")
    try:
        data = conn.recv(4096).decode().strip()
        if not data:
            conn.sendall(json.dumps({"codigo": 400, "mensaje": "Pedido vacío"}).encode())
            return
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            conn.sendall(json.dumps({"codigo": 400, "mensaje": "JSON inválido"}).encode())
            return

        task_id = uuid.uuid4().hex[:8]
        print(f"    Encolando {task_id}: {payload.get('accion')}")
        cola_tareas.put((task_id, payload))

        # Esperar resultado del worker
        inicio = time.time()
        resultado = None
        while time.time() - inicio < 15:
            with lock_resultados:
                if task_id in resultados:
                    resultado = resultados.pop(task_id)
                    break
            time.sleep(0.05)

        if resultado is None:
            resultado = {"codigo": 504, "mensaje": "Timeout esperando worker"}

        conn.sendall(json.dumps(resultado, ensure_ascii=False).encode())
    except Exception as e:
        print(f"Error: {e}")
        try:
            conn.sendall(json.dumps({"codigo": 500, "mensaje": str(e)}).encode())
        except Exception:
            pass
    finally:
        conn.close()
        print(f"[-] Conexión cerrada: {addr}")

def main():
    print("=" * 60)
    print("  SERVIDOR DISTRIBUIDO - PFO 3")
    print("  Rediseño del PFO 2 con sockets y worker pool")
    print("=" * 60)
    inicializar_db()
    print(f"[DB] Base '{DB}' lista.")

    # Levantar workers (threads con su pool)
    print(f"[SISTEMA] Iniciando {MAX_WORKERS} workers...")
    for i in range(1, MAX_WORKERS + 1):
        threading.Thread(target=worker_loop, args=(f"Worker-{i}",), daemon=True).start()

    # Servidor de entrada por socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind((HOST, PORT))
        servidor.listen()
        print(f"[SERVIDOR] Escuchando en {HOST}:{PORT}\n")
        while True:
            conn, addr = servidor.accept()
            threading.Thread(target=manejar_cliente, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()