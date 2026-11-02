import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key, required this.client});

  final ApiClient client;

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  bool _loading = true;
  String? _error;
  List<dynamic> _orders = [];
  List<dynamic> _profiles = [];
  List<dynamic> _notifications = [];

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
      widget.client.get('/api/v1/work-orders'),
      widget.client.get('/api/v1/technician-profiles'),
      widget.client.get('/api/v1/notifications'),
    ]);
    if (!results[0].ok) {
      setState(() {
        _loading = false;
        _error = (results[0].body is Map ? results[0].body['error'] : null) ?? 'Error';
      });
      return;
    }
    setState(() {
      _orders = results[0].body as List<dynamic>? ?? [];
      _profiles = results[1].ok ? (results[1].body as List<dynamic>? ?? []) : [];
      _notifications = results[2].ok ? (results[2].body as List<dynamic>? ?? []) : [];
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));
    final statuses = ['pending', 'assigned', 'in_progress', 'completed', 'closed', 'cancelled'];
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: statuses.map((s) {
              final count = _orders.where((o) => o['status'] == s).length;
              return SizedBox(
                width: 100,
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      children: [
                        Text('$count', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                        Text(s, style: const TextStyle(fontSize: 12)),
                      ],
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 16),
          const Text('Técnicos', style: TextStyle(fontWeight: FontWeight.bold)),
          ..._profiles.map((p) => ListTile(
                title: Text(p['user']?['username'] ?? ''),
                subtitle: Text(p['specialty'] ?? ''),
                trailing: Text(p['is_available'] == true ? 'Disponible' : 'No disponible'),
              )),
          const SizedBox(height: 16),
          const Text('Notificaciones recientes', style: TextStyle(fontWeight: FontWeight.bold)),
          ..._notifications.take(5).map((n) => ListTile(
                title: Text(n['subject'] ?? n['message'] ?? ''),
                subtitle: Text(n['status'] ?? ''),
              )),
        ],
      ),
    );
  }
}
