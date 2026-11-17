import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';
import '../../core/sync/sync_service.dart';
import '../dashboard/dashboard_page.dart';
import '../orders/orders_page.dart';
import '../notifications/notifications_page.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.client, required this.user, required this.onLogout});

  final ApiClient client;
  final Map<String, dynamic> user;
  final Future<void> Function() onLogout;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

enum _SyncState { idle, syncing, success, error }

class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {
  int _index = 0;
  late final SyncService _syncService;
  int _pendingCount = 0;
  _SyncState _syncState = _SyncState.idle;
  String? _syncMessage;
  bool _syncing = false;

  @override
  void initState() {
    super.initState();
    _syncService = SyncService(widget.client.baseUrl);
    WidgetsBinding.instance.addObserver(this);
    _refreshCount();
    _syncNow();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _syncNow();
    }
  }

  Future<void> _refreshCount() async {
    try {
      final c = await _syncService.pendingCount();
      if (mounted) setState(() => _pendingCount = c);
    } catch (_) {}
  }

  Future<void> _syncNow() async {
    if (_syncing) return;
    final token = widget.client.token;
    if (token == null) return;
    setState(() {
      _syncing = true;
      _syncState = _SyncState.syncing;
      _syncMessage = null;
    });
    try {
      final result = await _syncService.pushPending(token);
      await _refreshCount();
      if (mounted) {
        setState(() {
          _syncing = false;
          _syncState = _SyncState.success;
          _syncMessage = '${result.synced + result.duplicates} sincronizadas';
        });
      }
    } catch (_) {
      await _refreshCount();
      if (mounted) {
        setState(() {
          _syncing = false;
          _syncState = _SyncState.error;
          _syncMessage = 'Error de sincronizacion';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      DashboardPage(client: widget.client),
      OrdersPage(client: widget.client, user: widget.user),
      NotificationsPage(client: widget.client),
    ];
    return Scaffold(
      appBar: AppBar(
        title: const Text('SIGOS 2.0'),
        actions: [
          if (_pendingCount > 0)
            Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Chip(
                label: Text('$_pendingCount pendientes'),
                backgroundColor: Colors.orange.shade100,
              ),
            ),
          IconButton(
            onPressed: _syncing ? null : _syncNow,
            icon: _syncing
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.sync),
            tooltip: 'Sincronizar ahora',
          ),
          if (_syncMessage != null)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Center(
                child: Text(
                  _syncMessage!,
                  style: TextStyle(
                    color: _syncState == _SyncState.error ? Colors.red : Colors.green,
                    fontSize: 12,
                  ),
                ),
              ),
            ),
          IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout)),
        ],
      ),
      body: pages[_index],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: 'Dashboard'),
          BottomNavigationBarItem(icon: Icon(Icons.list_alt), label: 'Ordenes'),
          BottomNavigationBarItem(icon: Icon(Icons.notifications), label: 'Notif.'),
        ],
      ),
    );
  }
}
