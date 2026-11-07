import socket
import json

HOST = "127.0.0.1"
PORT = 5000

def enviar(payload: dict) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(json.dumps(payload).encode())
        return json.loads(s.recv(8192).decode())

def main():
    print("=" * 55)
    print("  CLIENTE TCP - SISTEMA DE TAREAS (PFO 3)")
    print("  Rediseño del PFO 2 con sockets y workers")
    print("=" * 55)
    while True:
        print("\n 1. Registrar usuario\n 2. Iniciar sesión (login)")
        print(" 3. Listar usuarios\n 4. Salir")
        op = input("Opción (1-4) > ").strip()

        if op == "1":
            u = input("Usuario: ").strip()
            p = input("Contraseña: ").strip()
            r = enviar({"accion": "registro", "usuario": u, "password": p})
            print(f"[{r['codigo']}] {r['mensaje']}  (worker: {r.get('worker')}, {r.get('ms')} ms)")
        elif op == "2":
            u = input("Usuario: ").strip()
            p = input("Contraseña: ").strip()
            r = enviar({"accion": "login", "usuario": u, "password": p})
            print(f"[{r['codigo']}] {r['mensaje']}  (worker: {r.get('worker')}, {r.get('ms')} ms)")
        elif op == "3":
            r = enviar({"accion": "listar"})
            if r["codigo"] == 200:
                print("Usuarios registrados:", ", ".join(r["usuarios"]) or "(ninguno)")
            else:
                print(f"[{r['codigo']}] {r['mensaje']}")
        elif op == "4":
            print("Chau.")
            break
        else:
            print("Opción inválida.")

if __name__ == "__main__":
    try:
        main()
    except ConnectionRefusedError:
        print("No se pudo conectar. ¿Está corriendo servidor.py?")