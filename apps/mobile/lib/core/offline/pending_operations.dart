import 'dart:convert';

import 'package:sqflite/sqflite.dart';
import 'package:uuid/uuid.dart';

import 'local_database.dart';

class PendingOperation {
  final String id;
  final String operationType;
  final Map<String, dynamic> payload;
  final String status;
  final String createdAt;

  PendingOperation({
    required this.id,
    required this.operationType,
    required this.payload,
    this.status = 'pending',
    required this.createdAt,
  });

  Map<String, dynamic> toJson() => {
        'client_operation_id': id,
        'operation_type': operationType,
        'payload': payload,
      };
}

class PendingOperationsStore {
  final LocalDatabase _db = LocalDatabase.instance;
  final _uuid = const Uuid();

  Future<PendingOperation> add(String operationType, Map<String, dynamic> payload) async {
    final db = await _db.database;
    final op = PendingOperation(
      id: _uuid.v4(),
      operationType: operationType,
      payload: payload,
      createdAt: DateTime.now().toIso8601String(),
    );
    await db.insert('pending_operations', {
      'id': op.id,
      'operation_type': op.operationType,
      'payload': jsonEncode(op.payload),
      'status': op.status,
      'created_at': op.createdAt,
    });
    return op;
  }

  Future<List<PendingOperation>> pending() async {
    final db = await _db.database;
    final rows = await db.query(
      'pending_operations',
      where: 'status = ?',
      whereArgs: ['pending'],
      orderBy: 'created_at ASC',
    );
    return rows.map((r) => PendingOperation(
      id: r['id'] as String,
      operationType: r['operation_type'] as String,
      payload: jsonDecode(r['payload'] as String) as Map<String, dynamic>,
      status: r['status'] as String,
      createdAt: r['created_at'] as String,
    )).toList();
  }

  Future<void> markSynced(String id) async {
    final db = await _db.database;
    await db.update('pending_operations', {'status': 'synced'}, where: 'id = ?', whereArgs: [id]);
  }

  Future<void> markFailed(String id) async {
    final db = await _db.database;
    await db.update('pending_operations', {'status': 'failed'}, where: 'id = ?', whereArgs: [id]);
  }

  Future<int> pendingCount() async {
    final db = await _db.database;
    final result = await db.rawQuery('SELECT COUNT(*) as c FROM pending_operations WHERE status = ?', ['pending']);
    return Sqflite.firstIntValue(result) ?? 0;
  }
}
