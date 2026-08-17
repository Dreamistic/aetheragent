import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_controller.dart';
import '../../l10n/app_localizations.dart';

class AuthPage extends ConsumerStatefulWidget {
  const AuthPage({super.key});

  @override
  ConsumerState<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends ConsumerState<AuthPage> {
  final _username = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _register = false;
  String? _localError;

  @override
  void dispose() {
    _username.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final state = ref.watch(appControllerProvider);
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Aether',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 28),
                TextField(
                  controller: _username,
                  decoration: InputDecoration(labelText: l10n.t('username')),
                  textInputAction: TextInputAction.next,
                ),
                if (_register) ...[
                  const SizedBox(height: 12),
                  TextField(
                    controller: _email,
                    decoration:
                        InputDecoration(labelText: l10n.t('emailOptional')),
                    textInputAction: TextInputAction.next,
                  ),
                ],
                const SizedBox(height: 12),
                TextField(
                  controller: _password,
                  decoration: InputDecoration(labelText: l10n.t('password')),
                  obscureText: true,
                  onSubmitted: (_) => _submit(),
                ),
                if (_localError != null || state.error != null) ...[
                  const SizedBox(height: 12),
                  Text(_localError ?? state.error!,
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 18),
                FilledButton(
                  onPressed: state.isLoading ? null : _submit,
                  child: Text(_register ? l10n.t('register') : l10n.t('login')),
                ),
                TextButton(
                  onPressed: () => setState(() {
                    _register = !_register;
                    _localError = null;
                  }),
                  child: Text(_register ? l10n.t('login') : l10n.t('register')),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _submit() async {
    final l10n = AppLocalizations.of(context);
    final username = _username.text.trim();
    final password = _password.text;
    if (username.isEmpty) {
      setState(() => _localError = l10n.t('usernameRequired'));
      return;
    }
    if (password.isEmpty) {
      setState(() => _localError = l10n.t('passwordRequired'));
      return;
    }
    if (_register && password.length < 6) {
      setState(() => _localError = l10n.t('passwordTooShort'));
      return;
    }
    setState(() => _localError = null);
    final controller = ref.read(appControllerProvider.notifier);
    if (_register) {
      await controller.register(username, password, _email.text.trim());
    } else {
      await controller.login(username, password);
    }
  }
}
