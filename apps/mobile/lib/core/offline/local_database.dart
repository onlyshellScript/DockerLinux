// Base de datos SQLite local para cache y operaciones pendientes.
import 'dart:convert';

import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

// Singleton de base de datos; crea tablas pending_operations, cached_*, sync_meta.
class LocalDatabase {
  LocalDatabase._();
  static final LocalDatabase instance = LocalDatabase._();

  Database? _db;

  // Devuelve la instancia abierta, abriendola la primera vez.
  Future<Database> get database async {
    if (_db != null) return _db!;
    _db = await _open();
    return _db!;
  }

  // Abre sigos.db en el directorio de bases de datos y ejecuta _onCreate en version 1.
  Future<Database> _open() async {
    final path = join(await getDatabasesPath(), 'sigos.db');
    return openDatabase(
      path,
      version: 1,
      onCreate: _onCreate,
    );
  }

  // Crea las tablas pending_operations, cached_work_orders, cached_materials y sync_meta.
  Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE pending_operations (
        id TEXT PRIMARY KEY,
        operation_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL
      )
    ''');

    await db.execute('''
      CREATE TABLE cached_work_orders (
        id INTEGER PRIMARY KEY,
        data TEXT NOT NULL,
        synced_at TEXT
      )
    ''');

    await db.execute('''
      CREATE TABLE cached_materials (
        id INTEGER PRIMARY KEY,
        data TEXT NOT NULL,
        synced_at TEXT
      )
    ''');

    await db.execute('''
      CREATE TABLE sync_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    ''');
  }

  // Cierra la base de datos abierta y libera la instancia en memoria.
  Future<void> close() async {
    await _db?.close();
    _db = null;
  }

  Future<void> cacheWorkOrders(List<dynamic> orders) async {
    final db = await database;
    final now = DateTime.now().toIso8601String();
    final batch = db.batch();
    for (final o in orders) {
      final m = o as Map<String, dynamic>;
      batch.insert(
        'cached_work_orders',
        {'id': m['id'] as int, 'data': jsonEncode(m), 'synced_at': now},
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  Future<List<Map<String, dynamic>>> cachedWorkOrders() async {
    final db = await database;
    final rows = await db.query('cached_work_orders');
    return rows.map((r) => jsonDecode(r['data'] as String) as Map<String, dynamic>).toList();
  }
}
