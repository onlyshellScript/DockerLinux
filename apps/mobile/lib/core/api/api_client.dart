import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiClient {
  ApiClient({required this.baseUrl, this.token});

  final String baseUrl;
  String? token;

  Map<String, String> _headers({bool json = true}) {
    final h = <String, String>{};
    if (json) h['Content-Type'] = 'application/json';
    if (token != null) h['Authorization'] = 'Bearer $token';
    return h;
  }

  Future<ApiResponse> get(String path, {Map<String, String>? query}) async {
    var uri = Uri.parse('$baseUrl$path');
    if (query != null) uri = uri.replace(queryParameters: query);
    final res = await http.get(uri, headers: _headers(json: false));
    return _parse(res);
  }

  Future<ApiResponse> post(String path, {Object? body}) async {
    final res = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: _headers(),
      body: body == null ? null : jsonEncode(body),
    );
    return _parse(res);
  }

  Future<ApiResponse> put(String path, {Object? body}) async {
    final res = await http.put(
      Uri.parse('$baseUrl$path'),
      headers: _headers(),
      body: body == null ? null : jsonEncode(body),
    );
    return _parse(res);
  }

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

class ApiResponse {
  const ApiResponse({required this.statusCode, this.body});

  final int statusCode;
  final dynamic body;

  bool get ok => statusCode >= 200 && statusCode < 300;
}
