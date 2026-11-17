import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';
import '../../core/offline/local_database.dart';
import 'order_detail_page.dart';

class OrdersPage extends StatefulWidget {
  const OrdersPage({super.key, required this.client, required this.user});

  final ApiClient client;
  final Map<String, dynamic> user;

  @override
  State<OrdersPage> createState() => _OrdersPageState();
}

class _OrdersPageState extends State<OrdersPage> {
  bool _loading = true;
  String? _error;
  List<dynamic> _orders = [];
  String _statusFilter = '';

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
    final query = _statusFilter.isEmpty ? null : {'status': _statusFilter};
    try {
      final res = await widget.client.get('/api/v1/work-orders', query: query);
      if (!res.ok) {
        setState(() {
          _loading = false;
          _error = (res.body is Map ? res.body['error'] : null) ?? 'Error';
        });
        return;
      }
      final orders = res.body as List<dynamic>? ?? [];
      setState(() {
        _orders = orders;
        _loading = false;
      });
      try {
        await LocalDatabase.instance.cacheWorkOrders(orders);
      } catch (_) {}
    } catch (_) {
      try {
        final cached = await LocalDatabase.instance.cachedWorkOrders();
        final filtered = _statusFilter.isEmpty
            ? cached
            : cached.where((o) => o['status'] == _statusFilter).toList();
        setState(() {
          _orders = filtered;
          _loading = false;
          _error = filtered.isEmpty ? 'Sin conexion' : null;
        });
      } catch (_) {
        setState(() {
          _loading = false;
          _error = 'Sin conexion';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(8),
          child: DropdownButton<String>(
            value: _statusFilter,
            items: const [
              DropdownMenuItem(value: '', child: Text('Todos')),
              DropdownMenuItem(value: 'pending', child: Text('pending')),
              DropdownMenuItem(value: 'assigned', child: Text('assigned')),
              DropdownMenuItem(value: 'in_progress', child: Text('in_progress')),
              DropdownMenuItem(value: 'completed', child: Text('completed')),
            ],
            onChanged: (v) {
              setState(() => _statusFilter = v ?? '');
              _load();
            },
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _load,
            child: ListView.builder(
              itemCount: _orders.length,
              itemBuilder: (context, i) {
                final o = _orders[i];
                return ListTile(
                  title: Text(o['title'] ?? ''),
                  subtitle: Text('${o['customer_name'] ?? ''} - ${o['status']}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => OrderDetailPage(client: widget.client, orderId: o['id'] as int, user: widget.user)),
                  ),
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}
