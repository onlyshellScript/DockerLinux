import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:sigos_mobile/core/offline/pending_operations.dart';
import 'package:sigos_mobile/core/sync/sync_service.dart';

class _FakeStore implements PendingOperationsRepository {
  final List<PendingOperation> _ops = [];
  final Set<String> _synced = {};

  @override
  Future<PendingOperation> add(String operationType, Map<String, dynamic> payload) async {
    final op = PendingOperation(
      id: 'op-${_ops.length + 1}',
      operationType: operationType,
      payload: payload,
      createdAt: DateTime.now().toIso8601String(),
    );
    _ops.add(op);
    return op;
  }

  @override
  Future<List<PendingOperation>> pending() async {
    return _ops.where((o) => !_synced.contains(o.id)).toList();
  }

  @override
  Future<void> markSynced(String id) async {
    _synced.add(id);
  }

  @override
  Future<void> markFailed(String id) async {}

  @override
  Future<int> pendingCount() async => (await pending()).length;
}

void main() {
  test('enqueue -> sync success -> queue empty', () async {
    final store = _FakeStore();
    final op = await store.add('change_status', {'work_order_id': 1, 'to_status': 'in_progress'});
    final client = MockClient((request) async {
      return http.Response(
        '{"results":[{"client_operation_id":"${op.id}","status":"synced"}]}',
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final sync = SyncService('http://localhost', client: client, store: store);
    final result = await sync.pushPending('token');
    expect(result.synced, 1);
    expect(await store.pendingCount(), 0);
  });

  test('network failure -> operation stays in queue', () async {
    final store = _FakeStore();
    await store.add('change_status', {'work_order_id': 1, 'to_status': 'in_progress'});
    final client = MockClient((request) async {
      throw Exception('no network');
    });
    final sync = SyncService('http://localhost', client: client, store: store);
    final result = await sync.pushPending('token');
    expect(result.failed, 1);
    expect(await store.pendingCount(), 1);
  });
}
