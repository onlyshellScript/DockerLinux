// Puerta de autenticacion: restaura sesion o muestra login/shell.
import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';
import '../../core/auth/session_store.dart';

import 'login_page.dart';
import '../shell/home_shell.dart';

// Widget que decide si mostrar login o la shell principal segun sesion.
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

// Estado: carga sesion, gestiona login/logout y construye la vista.
class _AuthGateState extends State<AuthGate> {
  final SessionStore _store = SessionStore();
  ApiClient? _client;
  Map<String, dynamic>? _user;
  bool _loading = true;

  @override
  // Restaura la sesion guardada en SQLite al iniciar el widget.
  void initState() {
    super.initState();
    _restore();
  }

  // Lee la sesion local y, si existe, crea ApiClient con su token y usuario.
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

  // Guarda la sesion recibida del login y actualiza el estado con cliente y usuario.
  void _onLogin(ApiClient client, Map<String, dynamic> user, String refresh) async {
    await _store.save(SessionData(accessToken: client.token!, refreshToken: refresh, user: user));
    // Actualiza _client y _user en el estado para reflejar el login exitoso y reconstruir la UI.
    setState(() {
      _client = client;
      _user = user;
    });
  }

  // Borra la sesion local y limpia cliente y usuario del estado.
  Future<void> _logout() async {
    // Revoca la sesion en el servidor (el token deja de servir aunque se reutilice); sin red se limpia igual.
    final session = await _store.load();
    final client = _client;
    if (client != null) {
      try {
        await client.post('/api/v1/auth/logout', body: {'refresh_token': session?.refreshToken ?? ''}).timeout(const Duration(seconds: 5));
      } catch (_) {}
    }
    await _store.clear();
    // Limpia cliente y usuario del estado tras cerrar sesion y reconstruye la UI.
    setState(() {
      _client = null;
      _user = null;
    });
  }

  @override
  // Muestra spinner mientras carga, login sin sesion o HomeShell con sesion.
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
