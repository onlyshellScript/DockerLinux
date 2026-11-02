import 'package:flutter/material.dart';

import '../../core/api/health_client.dart';

class HealthPage extends StatefulWidget {
  const HealthPage({super.key, this.client});

  final HealthClient? client;

  @override
  State<HealthPage> createState() => _HealthPageState();
}

class _HealthPageState extends State<HealthPage> {
  late final HealthClient _client =
      widget.client ?? HealthClient(const String.fromEnvironment('SIGOS_API_BASE_URL', defaultValue: 'http://10.0.2.2:5000'));

  HealthStatus _status = HealthStatus.unavailable;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _client.fetch();
      if (!mounted) return;
      setState(() {
        _status = result;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _status = HealthStatus.unavailable;
        _error = 'Error de comunicación';
        _loading = false;
      });
    }
  }

  @override
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
