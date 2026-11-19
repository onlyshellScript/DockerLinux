// Pantalla que muestra el estado de salud de la API central.
import 'package:flutter/material.dart';

import '../../core/api/health_client.dart';

// Widget con estado para consultar salud de la API.
class HealthPage extends StatefulWidget {
  const HealthPage({super.key, this.client});

  final HealthClient? client;

  @override
  State<HealthPage> createState() => _HealthPageState();
}

// Estado: cliente, status, loading y error.
class _HealthPageState extends State<HealthPage> {
  late final HealthClient _client =
      widget.client ?? HealthClient(const String.fromEnvironment('SIGOS_API_BASE_URL', defaultValue: 'http://10.0.2.2:5000'));

  HealthStatus _status = HealthStatus.unavailable;
  bool _loading = true;
  String? _error;

  @override
  // Consulta el estado de la API al iniciar la pantalla.
  void initState() {
    super.initState();
    _refresh();
  }

  // Llama a HealthClient.fetch y actualiza status o error de comunicacion.
  Future<void> _refresh() async {
    // Activa carga y limpia error antes de consultar la API.
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _client.fetch();
      if (!mounted) return;
      // Guarda el estado de salud recibido y desactiva carga.
      setState(() {
        _status = result;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      // Marca API no disponible y guarda error de comunicacion.
      setState(() {
        _status = HealthStatus.unavailable;
        _error = 'Error de comunicación';
        _loading = false;
      });
    }
  }

  @override
  // Construye indicador de color, texto y boton actualizar.
  Widget build(BuildContext context) {
    final color = _loading
        ? Colors.grey
        : (_status.isUp ? Colors.green : Colors.red);
    final text = _loading
        ? 'Comprobando...'
        : (_error ?? (_status.isUp ? 'API disponible' : 'API no disponible'));

    return Scaffold(
      appBar: AppBar(title: const Text('SIGOS 2.0')),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Estado de la API central'),
            const SizedBox(height: 16),
            Text(text, style: TextStyle(color: color, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _loading ? null : _refresh, child: const Text('Actualizar')),
          ],
        ),
      ),
    );
  }
}
