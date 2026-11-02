import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:sigos_mobile/core/api/health_client.dart';
import 'package:sigos_mobile/features/health/health_page.dart';

void main() {
  test('HealthClient reports available API', () async {
    final client = MockClient((request) async {
      return http.Response(
        jsonEncode({'status': 'UP', 'checks': {'application': 'UP', 'database': 'UP'}}),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final healthClient = HealthClient('http://localhost:8080', client: client);
    final result = await healthClient.fetch();
    expect(result.isUp, isTrue);
  });

  testWidgets('HealthPage shows available API', (tester) async {
    final client = MockClient((request) async {
      return http.Response(
        jsonEncode({'status': 'UP', 'checks': {'application': 'UP', 'database': 'UP'}}),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    await tester.pumpWidget(
      MaterialApp(home: HealthPage(client: HealthClient('http://localhost:8080', client: client))),
    );
    await tester.pumpAndSettle();
    expect(find.text('API disponible'), findsOneWidget);
  });
}
