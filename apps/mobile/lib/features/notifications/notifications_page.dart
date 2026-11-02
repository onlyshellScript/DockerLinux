import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';

class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key, required this.client});

  final ApiClient client;

  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends State<NotificationsPage> {
  bool _loading = true;
  String? _error;
  List<dynamic> _items = [];

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
    final res = await widget.client.get('/api/v1/notifications');
    if (!res.ok) {
      setState(() {
        _loading = false;
        _error = (res.body is Map ? res.body['error'] : null) ?? 'Error';
      });
      return;
    }
    setState(() {
      _items = res.body as List<dynamic>? ?? [];
      _loading = false;
    });
  }

  @override
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
