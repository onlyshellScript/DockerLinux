// Cliente y modelo de salud de la API para mostrar estado en la app.
import 'dart:convert';

import 'package:http/http.dart' as http;

// Estado de salud de la API: status, checks por componente y codigo HTTP.
class HealthStatus {
  const HealthStatus({required this.status, required this.checks, this.httpStatus});

  final String status;
  final Map<String, dynamic> checks;
  final int? httpStatus;

  bool get isUp => status == 'UP';

  // Construye HealthStatus desde JSON del endpoint /api/v1/health, tomando httpStatus opcional.
  factory HealthStatus.fromJson(Map<String, dynamic> json, {int? httpStatus}) {
    return HealthStatus(
      status: json['status'] as String? ?? 'DOWN',
      checks: (json['checks'] as Map<String, dynamic>?) ?? const <String, dynamic>{},
      httpStatus: httpStatus,
    );
  }

  static const HealthStatus unavailable = HealthStatus(
    status: 'DOWN',
    checks: <String, dynamic>{'application': 'UNKNOWN', 'database': 'UNKNOWN'},
  );
}

// Cliente HTTP para /api/v1/health que devuelve HealthStatus y lanza en error de red o parseo.
class HealthClient {
  HealthClient(this.baseUrl, {http.Client? client})
      : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  // Consulta /api/v1/health por red y parsea la respuesta en HealthStatus.
  Future<HealthStatus> fetch() async {
    final uri = Uri.parse('$baseUrl/api/v1/health');
    final response = await _client.get(uri);
    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    return HealthStatus.fromJson(decoded, httpStatus: response.statusCode);
  }
}
