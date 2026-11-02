import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';
import '../../core/auth/session_store.dart';

import 'login_page.dart';
import '../shell/home_shell.dart';

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  final SessionStore _store = SessionStore();
  ApiClient? _client;
  Map<String, dynamic>? _user;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    final session = await _store.load();
    if (session != null) {
      _client = ApiClient(
        baseUrl: const String.fromEnvironment('SIGOS_API_BASE_URL', defaultValue: 'http://10.0.2.2:5000'),
        token: session.accessToken,
      );
      _user = session.user;
    }
    if (mounted) setState(() => _loading = false);
  }

  void _onLogin(ApiClient client, Map<String, dynamic> user, String refresh) async {
    await _store.save(SessionData(accessToken: client.token!, refreshToken: refresh, user: user));
    setState(() {
      _client = client;
      _user = user;
    });
  }

  Future<void> _logout() async {
    await _store.clear();
    setState(() {
      _client = null;
      _user = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_client == null || _user == null) {
      return LoginPage(onLogin: _onLogin);
    }
    return HomeShell(client: _client!, user: _user!, onLogout: _logout);
  }
}
