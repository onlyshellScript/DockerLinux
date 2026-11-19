// Shell principal con barra inferior de navegacion entre secciones.
import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';
import '../dashboard/dashboard_page.dart';
import '../orders/orders_page.dart';
import '../notifications/notifications_page.dart';

// Widget con estado que contiene las pestanas principales.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.client, required this.user, required this.onLogout});

  final ApiClient client;
  final Map<String, dynamic> user;
  final Future<void> Function() onLogout;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

// Estado: indice de pestana seleccionada.
class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  // Construye AppBar, cuerpo segun pestana y barra inferior.
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
          IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout)),
        ],
      ),
      body: pages[_index],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: 'Dashboard'),
          BottomNavigationBarItem(icon: Icon(Icons.list_alt), label: 'Órdenes'),
          BottomNavigationBarItem(icon: Icon(Icons.notifications), label: 'Notif.'),
        ],
      ),
    );
  }
}
