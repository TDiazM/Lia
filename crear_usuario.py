"""
Crea un usuario de la plataforma (o cambia su contraseña). La contraseña se pide por teclado: no queda escrita en ningún lado.

Uso (desde esta carpeta):
    python crear_usuario.py <usuario> admin       # quien ofrece el servicio: panel /admin
    python crear_usuario.py <usuario> cliente     # el negocio que contrata: panel /cliente
    python crear_usuario.py <usuario> --cambiar   # cambia la contraseña de un usuario que ya existe
"""
import getpass
import sys

import auth


def main(argv):
    if len(argv) != 3 or (argv[2] not in auth.ROLES and argv[2] != "--cambiar"):
        print(__doc__)
        return 2
    usuario, accion = argv[1], argv[2]
    auth.iniciar()
    clave = getpass.getpass("Contraseña (mínimo %d caracteres): " % auth.CLAVE_MIN)
    if clave != getpass.getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden. No se hizo ningún cambio.")
        return 1
    try:
        if accion == "--cambiar":
            if not auth.cambiar_clave_usuario(usuario, clave):
                print("Ese usuario no existe.")
                return 1
            print("Contraseña cambiada. Se cerraron las sesiones abiertas de ese usuario.")
        else:
            auth.crear_usuario(usuario, clave, accion)
            print("Usuario '%s' creado con el rol '%s'." % (usuario, accion))
    except ValueError as e:
        print("No se pudo:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
