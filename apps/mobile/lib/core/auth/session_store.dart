import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../offline/local_database.dart';

class SessionData {
  const SessionData({required this.accessToken, required this.refreshToken, required this.user});

  final String accessToken;
  final String refreshToken;
  final Map<String, dynamic> user;
}

class SessionStore {
  final LocalDatabase _db = LocalDatabase.instance;

  Future<void> save(SessionData session) async {
    final db = await _db.database;
    await db.insert('sync_meta', {'key': 'access_token', 'value': session.accessToken}, conflictAlgorithm: ConflictAlgorithm.replace);
    await db.insert('sync_meta', {'key': 'refresh_token', 'value': session.refreshToken}, conflictAlgorithm: ConflictAlgorithm.replace);
    await db.insert('sync_meta', {'key': 'user', 'value': jsonEncode(session.user)}, conflictAlgorithm: ConflictAlgorithm.replace);
  }

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

  Future<void> clear() async {
    final db = await _db.database;
    await db.delete('sync_meta');
  }
}
