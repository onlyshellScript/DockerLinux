import 'package:flutter/material.dart';

import 'core/theme/app_theme.dart';
import 'features/auth/auth_gate.dart';

void main() {
  runApp(const SigosApp());
}

class SigosApp extends StatelessWidget {
  const SigosApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SIGOS',
      theme: AppTheme.light(),
      home: const AuthGate(),
    );
  }
}
