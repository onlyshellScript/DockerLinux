

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../../core/api/api_client.dart';

class OrderDetailPage extends StatefulWidget {
  const OrderDetailPage({super.key, required this.client, required this.orderId, required this.user});

  final ApiClient client;
  final int orderId;
  final Map<String, dynamic> user;

  @override
  State<OrderDetailPage> createState() => _OrderDetailPageState();
}

class _OrderDetailPageState extends State<OrderDetailPage> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _order;
  List<dynamic> _history = [];
  String? _newStatus;
  final _notes = TextEditingController();
  final _obs = TextEditingController();

  static const _baseUrl = String.fromEnvironment('SIGOS_API_BASE_URL', defaultValue: 'http://10.0.2.2:5000');

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final results = await Future.wait([
      widget.client.get('/api/v1/work-orders/${widget.orderId}'),
      widget.client.get('/api/v1/work-orders/${widget.orderId}/history'),
    ]);
    if (!results[0].ok) {
      setState(() {
        _loading = false;
        _error = (results[0].body is Map ? results[0].body['error'] : null) ?? 'Error';
      });
      return;
    }
    setState(() {
      _order = results[0].body as Map<String, dynamic>;
      _history = results[1].ok ? (results[1].body as List<dynamic>? ?? []) : [];
      _loading = false;
    });
  }

  List<String> _allowed(String status) {
    const t = {
      'pending': ['assigned', 'cancelled'],
      'assigned': ['in_progress', 'cancelled'],
      'in_progress': ['completed'],
      'completed': ['closed'],
      'closed': <String>[],
      'cancelled': <String>[],
    };
    return t[status] ?? <String>[];
  }

  Future<void> _changeStatus() async {
    if (_newStatus == null) return;
    final res = await widget.client.post('/api/v1/work-orders/${widget.orderId}/status', body: {
      'to_status': _newStatus,
      'notes': _notes.text.trim().isEmpty ? null : _notes.text.trim(),
    });
    if (!res.ok) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(res.body is Map ? res.body['error'] ?? 'Error' : 'Error')));
      return;
    }
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Estado actualizado')));
    _newStatus = null;
    _notes.clear();
    _load();
  }

  Future<void> _addObs() async {
    final desc = _obs.text.trim();
    if (desc.isEmpty) return;
    final uri = Uri.parse('$_baseUrl/api/v1/work-orders/${widget.orderId}/evidences');
    final req = http.MultipartRequest('POST', uri);
    if (widget.client.token != null) req.headers['Authorization'] = 'Bearer ${widget.client.token}';
    req.fields['evidence_type'] = 'observation';
    req.fields['description'] = desc;
    final streamed = await req.send();
    final res = await http.Response.fromStream(streamed);
    if (res.statusCode < 200 || res.statusCode >= 300) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: ${res.body}')));
      return;
    }
    _obs.clear();
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Observación agregada')));
    _load();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (_error != null) return Scaffold(appBar: AppBar(title: const Text('Detalle')), body: Center(child: Text(_error!)));
    final o = _order!;
    final allowed = _allowed(o['status'] as String);
    return Scaffold(
      appBar: AppBar(title: Text(o['title'] ?? '')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Estado: ${o['status']}', style: const TextStyle(fontWeight: FontWeight.bold)),
          Text('Cliente: ${o['customer_name'] ?? ''}'),
          Text('Dirección: ${o['address'] ?? ''}'),
          Text('Asignado: ${o['assigned_to']?['username'] ?? ''}'),
          const SizedBox(height: 16),
          if (allowed.isNotEmpty) ...[
            DropdownButton<String>(
              value: _newStatus,
              hint: const Text('Cambiar estado'),
              items: allowed.map((s) => DropdownMenuItem(value: s, child: Text(s))).toList(),
              onChanged: (v) => setState(() => _newStatus = v),
            ),
            TextField(controller: _notes, decoration: const InputDecoration(labelText: 'Notas')),
            const SizedBox(height: 8),
            ElevatedButton(onPressed: _changeStatus, child: const Text('Aplicar')),
          ],
          const SizedBox(height: 16),
          const Text('Historial', style: TextStyle(fontWeight: FontWeight.bold)),
          ..._history.map((h) => ListTile(
                title: Text('${h['from_status']} -> ${h['to_status']}'),
                subtitle: Text('${h['created_at']} ${h['notes'] ?? ''}'),
              )),
          const SizedBox(height: 16),
          TextField(controller: _obs, decoration: const InputDecoration(labelText: 'Nueva observación')),
          const SizedBox(height: 8),
          ElevatedButton(onPressed: _addObs, child: const Text('Agregar observación')),
        ],
      ),
    );
  }
}
