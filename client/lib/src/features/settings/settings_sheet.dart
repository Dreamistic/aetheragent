import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_controller.dart';
import '../../core/models.dart';
import '../../l10n/app_localizations.dart';

class SettingsSheet extends ConsumerWidget {
  const SettingsSheet({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(appControllerProvider);
    final controller = ref.read(appControllerProvider.notifier);
    final l10n = AppLocalizations.of(context);
    final apiController = TextEditingController(text: state.apiBaseUrl);
    return Padding(
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        bottom: MediaQuery.viewInsetsOf(context).bottom + 24,
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: ListView(
          shrinkWrap: true,
          children: [
            Text(l10n.t('settings'),
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: state.locale,
              decoration: InputDecoration(labelText: l10n.t('language')),
              items: const [
                DropdownMenuItem(value: 'zh-Hans', child: Text('简体中文')),
                DropdownMenuItem(value: 'zh-Hant', child: Text('繁體中文')),
                DropdownMenuItem(value: 'en', child: Text('English')),
              ],
              onChanged: (value) =>
                  value == null ? null : controller.updateLocale(value),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: state.theme,
              decoration: InputDecoration(labelText: l10n.t('theme')),
              items: [
                DropdownMenuItem(value: 'light', child: Text(l10n.t('light'))),
                DropdownMenuItem(value: 'dark', child: Text(l10n.t('dark'))),
                DropdownMenuItem(
                    value: 'system', child: Text(l10n.t('system'))),
              ],
              onChanged: (value) =>
                  value == null ? null : controller.updateTheme(value),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: apiController,
              decoration: InputDecoration(labelText: l10n.t('apiBase')),
              onSubmitted: controller.updateApiBaseUrl,
            ),
            const SizedBox(height: 12),
            SwitchListTile(
              value: state.contextAutoSwitchEnabled,
              title: Text(l10n.t('contextSwitch')),
              onChanged: controller.updateContextSwitch,
            ),
            const Divider(height: 28),
            _McpSection(
              servers: state.mcpServers,
              onAdd: () => _openMcpDialog(context, ref),
              onEdit: (server) => _openMcpDialog(context, ref, server: server),
              onToggle: (server, enabled) {
                controller.saveMcpServer(server.copyWith(enabled: enabled));
              },
              onTest: (server) async {
                try {
                  final tools =
                      await controller.refreshMcpServerTools(server.id);
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                        content: Text(
                            '${l10n.t('mcpToolCount')}: ${tools.isEmpty ? '0' : tools.join(', ')}')),
                  );
                } catch (error) {
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context)
                      .showSnackBar(SnackBar(content: Text(error.toString())));
                }
              },
              onDelete: controller.deleteMcpServer,
            ),
            const Divider(height: 28),
            Text(l10n.t('skills'),
                style: Theme.of(context).textTheme.titleMedium),
            if (state.skills.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(l10n.t('noSkills')),
              ),
            for (final skill in state.skills)
              ListTile(
                leading: Icon(skill.loaded
                    ? Icons.check_circle_outline
                    : Icons.error_outline),
                title: Text(skill.name),
                subtitle: Text(skill.description.isEmpty
                    ? skill.path
                    : '${skill.description}\n${skill.path}'),
                dense: true,
              ),
            const Divider(height: 28),
            Text(l10n.t('tools'),
                style: Theme.of(context).textTheme.titleMedium),
            for (final tool in state.tools)
              if (tool.source == 'mcp')
                ListTile(
                  leading: const Icon(Icons.extension_outlined),
                  title: Text(tool.name),
                  subtitle: Text(tool.description),
                  dense: true,
                )
              else
                SwitchListTile(
                  value: tool.enabled,
                  title: Text(tool.name),
                  subtitle: Text(tool.description),
                  onChanged: (enabled) =>
                      controller.toggleTool(tool.name, enabled),
                ),
            const Divider(height: 28),
            ListTile(
              leading: const Icon(Icons.person_outline),
              title: Text(state.user?.username ?? ''),
              subtitle: Text(state.user?.email ?? ''),
            ),
            OutlinedButton.icon(
              onPressed: () {
                Navigator.of(context).pop();
                controller.logout();
              },
              icon: const Icon(Icons.logout),
              label: Text(l10n.t('logout')),
            ),
          ],
        ),
      ),
    );
  }

  void _openMcpDialog(BuildContext context, WidgetRef ref,
      {McpServerConfig? server}) {
    showDialog<void>(
      context: context,
      builder: (_) => _McpServerDialog(
        server: server,
        onSave: (value) =>
            ref.read(appControllerProvider.notifier).saveMcpServer(value),
      ),
    );
  }
}

class _McpSection extends StatelessWidget {
  const _McpSection({
    required this.servers,
    required this.onAdd,
    required this.onEdit,
    required this.onToggle,
    required this.onTest,
    required this.onDelete,
  });

  final List<McpServerConfig> servers;
  final VoidCallback onAdd;
  final ValueChanged<McpServerConfig> onEdit;
  final void Function(McpServerConfig server, bool enabled) onToggle;
  final ValueChanged<McpServerConfig> onTest;
  final ValueChanged<String> onDelete;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(l10n.t('mcpServers'),
                style: Theme.of(context).textTheme.titleMedium),
            const Spacer(),
            TextButton.icon(
                onPressed: onAdd,
                icon: const Icon(Icons.add),
                label: Text(l10n.t('addMcpServer'))),
          ],
        ),
        if (servers.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(l10n.t('mcpNoServers'),
                style: Theme.of(context).textTheme.bodyMedium),
          ),
        for (final server in servers)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Switch(
                value: server.enabled,
                onChanged: (enabled) => onToggle(server, enabled)),
            title: Text(server.name),
            subtitle: Text(server.lastError?.isNotEmpty == true
                ? server.lastError!
                : (server.url ?? server.transport)),
            trailing: Wrap(
              spacing: 4,
              children: [
                IconButton(
                  onPressed: () => onTest(server),
                  icon: const Icon(Icons.sync_outlined),
                  tooltip: l10n.t('mcpTest'),
                ),
                IconButton(
                  onPressed: () => onEdit(server),
                  icon: const Icon(Icons.edit_outlined),
                  tooltip: l10n.t('editMcpServer'),
                ),
                IconButton(
                  onPressed: () => onDelete(server.id),
                  icon: const Icon(Icons.delete_outline),
                  tooltip: l10n.t('delete'),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _McpServerDialog extends StatefulWidget {
  const _McpServerDialog({required this.onSave, this.server});

  final McpServerConfig? server;
  final Future<void> Function(McpServerConfig server) onSave;

  @override
  State<_McpServerDialog> createState() => _McpServerDialogState();
}

class _McpServerDialogState extends State<_McpServerDialog> {
  late final TextEditingController _nameController;
  late final TextEditingController _urlController;
  late final TextEditingController _commandController;
  late final TextEditingController _argsController;
  late final TextEditingController _headersController;
  late final TextEditingController _timeoutController;
  String _transport = 'streamable_http';
  bool _enabled = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final server = widget.server;
    _nameController = TextEditingController(text: server?.name ?? '');
    _urlController = TextEditingController(text: server?.url ?? '');
    _commandController = TextEditingController(text: server?.command ?? '');
    _argsController = TextEditingController(
      text: server?.args.isNotEmpty == true
          ? const JsonEncoder.withIndent('  ').convert(server!.args)
          : '',
    );
    _headersController = TextEditingController(
      text: server?.headers.isNotEmpty == true
          ? const JsonEncoder.withIndent('  ').convert(server!.headers)
          : '',
    );
    _timeoutController =
        TextEditingController(text: (server?.timeoutSeconds ?? 30).toString());
    _transport = server?.transport ?? 'streamable_http';
    _enabled = server?.enabled ?? true;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _urlController.dispose();
    _commandController.dispose();
    _argsController.dispose();
    _headersController.dispose();
    _timeoutController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(widget.server == null
          ? l10n.t('addMcpServer')
          : l10n.t('editMcpServer')),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                  controller: _nameController,
                  decoration: InputDecoration(labelText: l10n.t('mcpName'))),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _transport,
                decoration: InputDecoration(labelText: l10n.t('mcpTransport')),
                items: const [
                  DropdownMenuItem(
                      value: 'streamable_http', child: Text('Streamable HTTP')),
                  DropdownMenuItem(value: 'sse', child: Text('SSE')),
                  DropdownMenuItem(value: 'stdio', child: Text('stdio')),
                ],
                onChanged: (value) =>
                    setState(() => _transport = value ?? _transport),
              ),
              const SizedBox(height: 12),
              if (_transport == 'stdio') ...[
                TextField(
                  controller: _commandController,
                  decoration:
                      InputDecoration(labelText: l10n.t('mcpCommand')),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _argsController,
                  decoration: InputDecoration(labelText: l10n.t('mcpArgs')),
                  minLines: 1,
                  maxLines: 4,
                ),
              ] else ...[
                TextField(
                    controller: _urlController,
                    decoration: InputDecoration(labelText: l10n.t('mcpUrl'))),
                const SizedBox(height: 12),
                TextField(
                  controller: _headersController,
                  decoration: InputDecoration(labelText: l10n.t('mcpHeaders')),
                  minLines: 2,
                  maxLines: 5,
                ),
              ],
              const SizedBox(height: 12),
              TextField(
                controller: _timeoutController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(labelText: l10n.t('mcpTimeout')),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: _enabled,
                title: Text(l10n.t('enabled')),
                onChanged: (value) => setState(() => _enabled = value),
              ),
              if (_error != null)
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(_error!,
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error)),
                ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
            onPressed: _saving ? null : () => Navigator.of(context).pop(),
            child: Text(l10n.t('cancel'))),
        FilledButton(
            onPressed: _saving ? null : _save, child: Text(l10n.t('save'))),
      ],
    );
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final headersText = _headersController.text.trim();
      final headers =
          headersText.isEmpty ? <String, String>{} : _parseHeaders(headersText);
      final argsText = _argsController.text.trim();
      final args = argsText.isEmpty ? <String>[] : _parseArgs(argsText);
      final server = McpServerConfig(
        id: widget.server?.id ?? '',
        name: _nameController.text.trim(),
        transport: _transport,
        url: _urlController.text.trim(),
        command: _commandController.text.trim(),
        args: args,
        headers: headers,
        enabled: _enabled,
        timeoutSeconds: int.tryParse(_timeoutController.text.trim()) ?? 30,
      );
      await widget.onSave(server);
      if (mounted) Navigator.of(context).pop();
    } catch (error) {
      setState(() {
        _saving = false;
        _error = error.toString();
      });
    }
  }

  Map<String, String> _parseHeaders(String text) {
    final decoded = jsonDecode(text);
    if (decoded is! Map) {
      throw const FormatException('Headers must be a JSON object');
    }
    return decoded
        .map((key, value) => MapEntry(key.toString(), value.toString()));
  }

  List<String> _parseArgs(String text) {
    final decoded = jsonDecode(text);
    if (decoded is! List) {
      throw const FormatException('Args must be a JSON array');
    }
    return decoded.map((item) => item.toString()).toList();
  }
}
