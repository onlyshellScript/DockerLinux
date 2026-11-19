import os, shutil, glob, datetime

# Genera una copia de seguridad del archivo SQLite indicado en src_path dentro de dst_dir con marca de tiempo; conserva solo las últimas 'retention' copias eliminando las antiguas; devuelve la ruta del backup creado.
def backup(src_path, dst_dir, retention=7):
    os.makedirs(dst_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(dst_dir, f"backup_{ts}.db")
    shutil.copy2(src_path, dst)
    # Aplica política de retención: elimina las copias de seguridad más antiguas que excedan el límite configurado.
    files = sorted(glob.glob(os.path.join(dst_dir, "backup_*.db")), reverse=True)
    for f in files[retention:]:
        try:
            os.remove(f)
        except OSError:
            pass
    return dst

# Restaura un backup copiándolo sobre dst_path; devuelve la ruta destino. Efecto secundario: sobrescribe el archivo existente en dst_path.
def restore(backup_path, dst_path):
    shutil.copy2(backup_path, dst_path)
    return dst_path

if __name__ == "__main__":
    src = os.getenv("SIGOS_DB_PATH", "sigos.db")
    dst_dir = os.getenv("SIGOS_BACKUP_DIR", "backups")
    retention = int(os.getenv("SIGOS_BACKUP_RETENTION", "7"))
    print("backup:", backup(src, dst_dir, retention))
