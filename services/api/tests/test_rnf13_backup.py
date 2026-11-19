# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.

import os, sqlite3, sys, tempfile
sys.path.insert(0, r"C:\Users\braya\Documents\SIGOSV\scripts")
from backup_sqlite import backup, restore
# test_rnf13_backup_restore_counts: valida el escenario rnf13 backup restore counts preparando datos, ejecutando la accion y comprobando el resultado esperado.

def test_rnf13_backup_restore_counts():
    d = tempfile.mkdtemp()
    src = os.path.join(d, "src.db")
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES ('a')")
    conn.commit()
    conn.close()

    bdir = os.path.join(d, "backups")
    bp = backup(src, bdir, retention=2)
    assert os.path.exists(bp)

    restored = os.path.join(d, "restored.db")
    restore(bp, restored)
    conn = sqlite3.connect(restored)
    count = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    conn.close()
    assert count == 1
