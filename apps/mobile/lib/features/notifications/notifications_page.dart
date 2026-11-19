// Pantalla de listado de notificaciones del usuario.
import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';

// Widget con estado para cargar notificaciones.
class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key, required this.client});

  final ApiClient client;

  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

// Estado: loading, error y lista de notificaciones.
class _NotificationsPageState extends State<NotificationsPage> {
  bool _loading = true;
  String? _error;
  List<dynamic> _items = [];

  @override
  // Inicia la carga de notificaciones al montar el widget.
  void initState() {
    super.initState();
    _load();
  }

  // Consulta /api/v1/notifications y actualiza la lista o el error.
  Future<void> _load() async {
    // Activa carga y limpia error antes de consultar notificaciones.
    setState(() {
      _loading = true;
      _error = null;
    });
    final res = await widget.client.get('/api/v1/notifications');
    if (!res.ok) {
      // Desactiva carga y guarda el error si falla la consulta.
      setState(() {
        _loading = false;
        _error = (res.body is Map ? res.body['error'] : null) ?? 'Error';
      });
      return;
    }
    // Guarda notificaciones recibidas y desactiva carga.
    setState(() {
      _items = res.body as List<dynamic>? ?? [];
      _loading = false;
    });
  }

  @override
  // Construye lista con pull-to-refresh o indicador de carga/error.
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        children: _items.map((n) => ListTile(
              title: Text(n['subject'] ?? ''),
              subtitle: Text(n['message'] ?? ''),
              trailing: Text(n['status'] ?? ''),
            )).toList(),
      ),
    );
  }
}
