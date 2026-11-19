// Pantalla de listado de ordenes de trabajo con filtro por estado.
import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';
import 'order_detail_page.dart';

// Widget con estado que muestra ordenes y permite filtrar.
class OrdersPage extends StatefulWidget {
  const OrdersPage({super.key, required this.client, required this.user});

  final ApiClient client;
  final Map<String, dynamic> user;

  @override
  State<OrdersPage> createState() => _OrdersPageState();
}

// Estado: loading, error, lista de ordenes y filtro de estado.
class _OrdersPageState extends State<OrdersPage> {
  bool _loading = true;
  String? _error;
  List<dynamic> _orders = [];
  String _statusFilter = '';

  @override
  // Inicia la carga de ordenes al montar el widget.
  void initState() {
    super.initState();
    _load();
  }

  // Consulta ordenes con filtro por estado y actualiza la lista o el error.
  Future<void> _load() async {
    // Activa carga y limpia error antes de consultar ordenes.
    setState(() {
      _loading = true;
      _error = null;
    });
    final query = _statusFilter.isEmpty ? null : {'status': _statusFilter};
    final res = await widget.client.get('/api/v1/work-orders', query: query);
    if (!res.ok) {
      // Desactiva carga y guarda el error si falla la consulta.
      setState(() {
        _loading = false;
        _error = (res.body is Map ? res.body['error'] : null) ?? 'Error';
      });
      return;
    }
    // Guarda ordenes recibidas y desactiva carga.
    setState(() {
      _orders = res.body as List<dynamic>? ?? [];
      _loading = false;
    });
  }

  @override
  // Construye filtro desplegable y lista con navegacion a detalle.
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
