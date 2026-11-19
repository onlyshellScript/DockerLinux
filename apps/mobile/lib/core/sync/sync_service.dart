// Sincronizacion bidireccional de operaciones pendientes con la API.
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../offline/pending_operations.dart';

// Resultado de sincronizacion: contadores de sincronizados, fallidos y duplicados.
class SyncResult {
  final int synced;
  final int failed;
  final int duplicates;

  SyncResult({required this.synced, required this.failed, required this.duplicates});
}

// Servicio que envia operaciones pendientes (push) y descarga cambios (pull).
class SyncService {
  SyncService(this.baseUrl, {http.Client? client, PendingOperationsRepository? store})
      : _client = client ?? http.Client(),
        _store = store ?? PendingOperationsStore();

  final String baseUrl;
  final http.Client _client;
  final PendingOperationsRepository _store;

  // Envia operaciones pending a /api/v1/sync/push y actualiza su estado segun respuesta.
  Future<SyncResult> pushPending(String token) async {
    final pending = await _store.pending();
    if (pending.isEmpty) {
      return SyncResult(synced: 0, failed: 0, duplicates: 0);
    }

    final uri = Uri.parse('$baseUrl/api/v1/sync/push');
    http.Response response;
    try {
      response = await _client.post(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'operations': pending.map((op) => op.toJson()).toList(),
        }),
      );
    } catch (_) {
      return SyncResult(synced: 0, failed: pending.length, duplicates: 0);
    }

    if (response.statusCode != 200) {
      return SyncResult(synced: 0, failed: pending.length, duplicates: 0);
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final results = body['results'] as List<dynamic>;

    int synced = 0, failed = 0, duplicates = 0;
    for (final r in results) {
      final status = r['status'] as String;
      final opId = r['client_operation_id'] as String;
      if (status == 'synced') {
        await _store.markSynced(opId);
        synced++;
      } else if (status == 'duplicate') {
        await _store.markSynced(opId);
        duplicates++;
      } else {
        await _store.markFailed(opId);
        failed++;
      }
    }
    return SyncResult(synced: synced, failed: failed, duplicates: duplicates);
  }

  // Descarga cambios desde /api/v1/sync/pull con filtro opcional since.
  Future<Map<String, dynamic>> pull(String token, {String? since}) async {
    var uri = Uri.parse('$baseUrl/api/v1/sync/pull');
    if (since != null) {
      uri = uri.replace(queryParameters: {'since': since});
    }
    final response = await _client.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) {
      throw Exception('Pull failed: ${response.statusCode}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  // Delega el conteo de operaciones pending al store local.
  Future<int> pendingCount() => _store.pendingCount();
}
