import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:sigos_mobile/core/sync/sync_service.dart';

void main() {
  test('SyncService pull returns server time and data', () async {
    final client = MockClient((request) async {
      return http.Response(
        jsonEncode({
          'server_time': '2026-01-01T00:00:00Z',
          'work_orders': [],
          'materials': [],
        }),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final sync = SyncService('http://localhost:5000', client: client);
    final data = await sync.pull('fake-token');
    expect(data['server_time'], '2026-01-01T00:00:00Z');
    expect(data['work_orders'], isEmpty);
    expect(data['materials'], isEmpty);
  });

  test('SyncService pull with since parameter', () async {
    String? capturedSince;
    final client = MockClient((request) async {
      capturedSince = request.url.queryParameters['since'];
      return http.Response(
        jsonEncode({'server_time': '2026-01-02T00:00:00Z', 'work_orders': [], 'materials': []}),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final sync = SyncService('http://localhost:5000', client: client);
    await sync.pull('fake-token', since: '2026-01-01T00:00:00Z');
    expect(capturedSince, '2026-01-01T00:00:00Z');
  });
}
