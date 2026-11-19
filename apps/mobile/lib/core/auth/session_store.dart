// Persistencia local de la sesion de usuario con SQLite (sqflite).
import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../offline/local_database.dart';

// Datos de sesion: tokens de acceso/refresco y perfil de usuario.
class SessionData {
  const SessionData({required this.accessToken, required this.refreshToken, required this.user});

  final String accessToken;
  final String refreshToken;
  final Map<String, dynamic> user;
}

// Guarda, carga y borra la sesion en la tabla sync_meta de SQLite.
class SessionStore {
  final LocalDatabase _db = LocalDatabase.instance;

  // Inserta o reemplaza access_token, refresh_token y user en sync_meta.
  Future<void> save(SessionData session) async {
    final db = await _db.database;
    await db.insert('sync_meta', {'key': 'access_token', 'value': session.accessToken}, conflictAlgorithm: ConflictAlgorithm.replace);
    await db.insert('sync_meta', {'key': 'refresh_token', 'value': session.refreshToken}, conflictAlgorithm: ConflictAlgorithm.replace);
    await db.insert('sync_meta', {'key': 'user', 'value': jsonEncode(session.user)}, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  // Lee sync_meta y reconstruye SessionData; devuelve null si no hay access_token.
  Future<SessionData?> load() async {
    final db = await _db.database;
    final rows = await db.query('sync_meta');
    final map = {for (final r in rows) r['key'] as String: r['value'] as String};
    if (!map.containsKey('access_token')) return null;
    return SessionData(
      accessToken: map['access_token']!,
      refreshToken: map['refresh_token'] ?? '',
      user: jsonDecode(map['user'] ?? '{}') as Map<String, dynamic>,
    );
  }

  // Cierra la sesion local: borra tokens y usuario (sync_meta) y los datos del servidor guardados en cache
  // (ordenes y materiales), para que la siguiente cuenta en el equipo no vea informacion de la anterior.
  // Las operaciones pendientes de sincronizar no se borran aqui para no perder trabajo sin enviar.
  Future<void> clear() async {
    final db = await _db.database;
    await db.transaction((txn) async {
      await txn.delete('sync_meta');
      await txn.delete('cached_work_orders');
      await txn.delete('cached_materials');
    });
  }
}
