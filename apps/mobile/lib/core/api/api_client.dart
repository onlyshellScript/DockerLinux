// Cliente HTTP base para consumir la API REST de SIGOS desde la app movil.
import 'dart:convert';

import 'package:http/http.dart' as http;

// Cliente HTTP con baseUrl y token JWT opcional; expone get/post/put y parseo.
class ApiClient {
  ApiClient({required this.baseUrl, this.token});

  final String baseUrl;
  String? token;

  // Arma headers HTTP con Content-Type JSON y token Bearer si hay sesion activa.
  Map<String, String> _headers({bool json = true}) {
    final h = <String, String>{};
    if (json) h['Content-Type'] = 'application/json';
    if (token != null) h['Authorization'] = 'Bearer $token';
    return h;
  }

  // Envía GET a path con query opcional y devuelve ApiResponse parseado; solo lectura de red.
  Future<ApiResponse> get(String path, {Map<String, String>? query}) async {
    var uri = Uri.parse('$baseUrl$path');
    if (query != null) uri = uri.replace(queryParameters: query);
    final res = await http.get(uri, headers: _headers(json: false));
    return _parse(res);
  }

  // Envía POST con body JSON opcional y devuelve ApiResponse parseado; escritura remota.
  Future<ApiResponse> post(String path, {Object? body}) async {
    final res = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: _headers(),
      body: body == null ? null : jsonEncode(body),
    );
    return _parse(res);
  }

  // Envía PUT con body JSON opcional y devuelve ApiResponse parseado; actualizacion remota.
  Future<ApiResponse> put(String path, {Object? body}) async {
    final res = await http.put(
      Uri.parse('$baseUrl$path'),
      headers: _headers(),
      body: body == null ? null : jsonEncode(body),
    );
    return _parse(res);
  }

  // Parsea la respuesta HTTP: decodifica JSON si es posible o conserva texto.
  ApiResponse _parse(http.Response res) {
    dynamic body;
    try {
      body = res.body.isEmpty ? null : jsonDecode(res.body);
    } catch (_) {
      body = res.body;
    }
    return ApiResponse(statusCode: res.statusCode, body: body);
  }
}

// Respuesta HTTP normalizada con codigo de estado y cuerpo dinamico.
class ApiResponse {
  const ApiResponse({required this.statusCode, this.body});

  final int statusCode;
  final dynamic body;

  bool get ok => statusCode >= 200 && statusCode < 300;
}
