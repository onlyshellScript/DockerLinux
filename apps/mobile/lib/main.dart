// Punto de entrada y configuracion global de la app Flutter SIGOS 2.0.
import 'package:flutter/material.dart';

import 'core/theme/app_theme.dart';
import 'features/auth/auth_gate.dart';

// Arranca la aplicacion Flutter con el widget raiz SigosApp.
void main() {
  runApp(const SigosApp());
}

// Widget raiz: configura tema claro y la puerta de autenticacion.
class SigosApp extends StatelessWidget {
  const SigosApp({super.key});

  @override
  // Construye el MaterialApp con titulo, tema y AuthGate como home.
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SIGOS',
      theme: AppTheme.light(),
      home: const AuthGate(),
    );
  }
}
