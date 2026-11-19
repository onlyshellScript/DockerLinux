// Pantalla de inicio de sesion con usuario y contrasena.
import 'package:flutter/material.dart';

import '../../core/api/api_client.dart';


// Widget publico de la pagina de login.
class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.onLogin});

  final void Function(ApiClient client, Map<String, dynamic> user, String refresh) onLogin;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

// Estado: controladores, carga y error; envia credenciales a la API.
class _LoginPageState extends State<LoginPage> {
  final _username = TextEditingController();
  final _password = TextEditingController();
  bool _loading = false;
  String? _error;

  static const _baseUrl = String.fromEnvironment('SIGOS_API_BASE_URL', defaultValue: 'http://10.0.2.2:5000');

  // Envia credenciales a /api/v1/auth/login y, si OK, entrega sesion al padre.
  Future<void> _submit() async {
    // Marca carga activa y limpia el error previo antes de enviar credenciales.
    setState(() {
      _loading = true;
      _error = null;
    });
    final client = ApiClient(baseUrl: _baseUrl);
    final res = await client.post('/api/v1/auth/login', body: {
      'username': _username.text.trim(),
      'password': _password.text,
    });
    if (!res.ok) {
      // Desactiva carga y guarda el mensaje de error tras login fallido.
      setState(() {
        _loading = false;
        _error = (res.body is Map ? res.body['error'] : null) ?? 'Credenciales inválidas';
      });
      return;
    }
    final body = res.body as Map<String, dynamic>;
    client.token = body['access_token'] as String;
    setState(() => _loading = false);
    widget.onLogin(client, body['user'] as Map<String, dynamic>, body['refresh_token'] as String);
  }

  @override
  // Construye el formulario centrado con campos y boton ingresar.
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 360),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('SIGOS 2.0', style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: const Color(0xFF103020))),
                    const SizedBox(height: 8),
                    const Text('Inicio de sesión'),
                    const SizedBox(height: 16),
                    if (_error != null) ...[
                      Text(_error!, style: const TextStyle(color: Colors.red)),
                      const SizedBox(height: 8),
                    ],
                    TextField(controller: _username, decoration: const InputDecoration(labelText: 'Usuario')),
                    const SizedBox(height: 12),
                    TextField(controller: _password, obscureText: true, decoration: const InputDecoration(labelText: 'Contraseña')),
                    const SizedBox(height: 16),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _loading ? null : _submit,
                        child: Text(_loading ? 'Ingresando...' : 'Ingresar'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
