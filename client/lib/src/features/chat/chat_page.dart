import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_controller.dart';
import '../../core/app_fonts.dart';
import '../../core/models.dart';
import '../../l10n/app_localizations.dart';
import '../settings/settings_sheet.dart';
import 'message_renderer.dart';

class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});

  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<ImageAttachmentData> _images = [];
  bool _sidebarCollapsed = false;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AppState>(appControllerProvider, (previous, next) {
      final request = next.pendingClientRequest;
      if (request == null ||
          identical(previous?.pendingClientRequest, request)) {
        return;
      }
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        _handlePendingClientRequest(request);
      });
    });
    final state = ref.watch(appControllerProvider);
    final l10n = AppLocalizations.of(context);
    var currentTitle = l10n.t('chatTitle');
    for (final session in state.sessions) {
      if (session.id == state.currentSessionId) {
        currentTitle = session.title;
        break;
      }
    }
    return Scaffold(
      body: Row(
        children: [
          if (!_sidebarCollapsed)
            _Sidebar(
              sessions: state.sessions,
              currentSessionId: state.currentSessionId,
              user: state.user,
              onNew: () =>
                  ref.read(appControllerProvider.notifier).newSession(),
              onSelect: (id) =>
                  ref.read(appControllerProvider.notifier).switchSession(id),
              onSettings: _openSettings,
              onEditProfile: _openProfileDialog,
              onLogout: () => ref.read(appControllerProvider.notifier).logout(),
            ),
          Expanded(
            child: Column(
              children: [
                _TopBar(
                  title: currentTitle,
                  isSidebarCollapsed: _sidebarCollapsed,
                  onToggleSidebar: () =>
                      setState(() => _sidebarCollapsed = !_sidebarCollapsed),
                  onSettings: _openSettings,
                ),
                if (state.error != null)
                  MaterialBanner(
                    content: Text(state.error!),
                    actions: [
                      TextButton(onPressed: () {}, child: const Text('OK'))
                    ],
                  ),
                Expanded(
                  child: _ChatBackground(
                    child: state.messages.isEmpty
                        ? _EmptyState(
                            l10n: l10n,
                            onSuggestion: (text) {
                              _controller.text = text;
                              _controller.selection =
                                  TextSelection.collapsed(offset: text.length);
                            },
                          )
                        : ListView.builder(
                            controller: _scrollController,
                            padding: const EdgeInsets.symmetric(
                                horizontal: 28, vertical: 20),
                            itemCount: state.messages.length,
                            itemBuilder: (context, index) =>
                                _MessageTile(message: state.messages[index]),
                          ),
                  ),
                ),
                _Composer(
                  controller: _controller,
                  images: _images,
                  isStreaming: state.isStreaming,
                  hint: l10n.t('messageHint'),
                  onPickImage: _pickImages,
                  onRemoveImage: (index) =>
                      setState(() => _images.removeAt(index)),
                  onSend: _send,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _pickImages() async {
    final result = await FilePicker.platform
        .pickFiles(type: FileType.image, allowMultiple: true, withData: true);
    if (result == null) return;
    setState(() {
      for (final file in result.files) {
        final bytes = file.bytes;
        if (bytes == null) continue;
        final mime = _mimeFromName(file.name);
        _images.add(ImageAttachmentData(
            data: 'data:$mime;base64,${base64Encode(bytes)}', mimeType: mime));
      }
    });
  }

  String _mimeFromName(String name) {
    final lower = name.toLowerCase();
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
    if (lower.endsWith('.webp')) return 'image/webp';
    return 'image/png';
  }

  Future<void> _send() async {
    final text = _controller.text;
    final images = List<ImageAttachmentData>.from(_images);
    _controller.clear();
    setState(_images.clear);
    await ref
        .read(appControllerProvider.notifier)
        .sendMessage(text, images: images);
    await Future<void>.delayed(const Duration(milliseconds: 80));
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
      );
    }
  }

  void _openSettings() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (_) => const SettingsSheet(),
    );
  }

  void _openProfileDialog() {
    showDialog<void>(
      context: context,
      builder: (_) => _ProfileDialog(
        user: ref.read(appControllerProvider).user,
        onSave: ({required username, required displayName, avatarData}) {
          return ref.read(appControllerProvider.notifier).updateProfile(
                username: username,
                displayName: displayName,
                avatarData: avatarData,
              );
        },
      ),
    );
  }

  Future<void> _handlePendingClientRequest(Map<String, dynamic> request) async {
    final type = request['type'] as String?;
    final data = request['data'];
    if (data is! Map) {
      ref.read(appControllerProvider.notifier).clearPendingClientRequest();
      return;
    }
    final payload = Map<String, dynamic>.from((data['payload'] as Map?) ?? {});
    if (type == 'ask_for_info_request') {
      await _showAskForInfoDialog(payload);
      return;
    }
    if (type == 'confirmation_request') {
      await _showConfirmationDialog(payload);
      return;
    }
    ref.read(appControllerProvider.notifier).clearPendingClientRequest();
  }

  Future<void> _showAskForInfoDialog(Map<String, dynamic> payload) async {
    final l10n = AppLocalizations.of(context);
    final meta = Map<String, dynamic>.from((payload['meta'] as Map?) ?? {});
    final rawQuestions =
        ((payload['questions'] as List?) ?? []).whereType<Map>().toList();
    final questions = rawQuestions.isEmpty
        ? <Map<String, dynamic>>[
            {'id': 'response', 'label': l10n.t('messageHint')},
          ]
        : rawQuestions.map((item) => Map<String, dynamic>.from(item)).toList();
    final controllers = <String, TextEditingController>{};
    for (var i = 0; i < questions.length; i++) {
      final id = _questionId(questions[i], i);
      controllers[id] = TextEditingController();
    }

    final answers = await showDialog<Map<String, String>>(
      context: context,
      barrierDismissible: false,
      builder: (context) {
        return AlertDialog(
          title: Text((meta['title'] as String?)?.trim().isNotEmpty == true
              ? meta['title'] as String
              : '需要补充信息'),
          content: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (var i = 0; i < questions.length; i++) ...[
                    TextField(
                      controller: controllers[_questionId(questions[i], i)],
                      minLines: 1,
                      maxLines: 4,
                      decoration: InputDecoration(
                        labelText: _questionLabel(questions[i], i),
                        hintText: questions[i]['placeholder'] as String?,
                      ),
                    ),
                    if (i != questions.length - 1) const SizedBox(height: 12),
                  ],
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(null),
              child: Text(l10n.t('cancel')),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(context).pop({
                  for (var i = 0; i < questions.length; i++)
                    _questionLabel(questions[i], i):
                        controllers[_questionId(questions[i], i)]!.text.trim(),
                });
              },
              child: Text(l10n.t('save')),
            ),
          ],
        );
      },
    );
    for (final controller in controllers.values) {
      controller.dispose();
    }
    ref.read(appControllerProvider.notifier).clearPendingClientRequest();
    if (answers == null || answers.values.every((value) => value.isEmpty)) {
      return;
    }
    final text = [
      '我补充的信息如下：',
      for (final entry in answers.entries)
        if (entry.value.isNotEmpty) '- ${entry.key}: ${entry.value}',
    ].join('\n');
    await Future<void>.delayed(const Duration(milliseconds: 120));
    if (mounted) {
      await ref.read(appControllerProvider.notifier).sendMessage(text);
    }
  }

  Future<void> _showConfirmationDialog(Map<String, dynamic> payload) async {
    final l10n = AppLocalizations.of(context);
    final description = (payload['description'] as String?)?.trim() ?? '';
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('请确认'),
        content: Text(description.isEmpty ? '是否继续执行该操作？' : description),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(l10n.t('cancel'))),
          FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('确认')),
        ],
      ),
    );
    ref.read(appControllerProvider.notifier).clearPendingClientRequest();
    final text =
        confirmed == true ? '我确认继续执行：$description' : '我取消执行：$description';
    await Future<void>.delayed(const Duration(milliseconds: 120));
    if (mounted) {
      await ref.read(appControllerProvider.notifier).sendMessage(text);
    }
  }

  String _questionId(Map<String, dynamic> question, int index) {
    final raw =
        question['id'] ?? question['key'] ?? question['name'] ?? 'field_$index';
    return raw.toString();
  }

  String _questionLabel(Map<String, dynamic> question, int index) {
    final raw = question['label'] ??
        question['question'] ??
        question['title'] ??
        question['text'];
    final label = raw?.toString().trim();
    return label == null || label.isEmpty ? '问题 ${index + 1}' : label;
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.title,
    required this.isSidebarCollapsed,
    required this.onToggleSidebar,
    required this.onSettings,
  });
  final String title;
  final bool isSidebarCollapsed;
  final VoidCallback onToggleSidebar;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 56,
      decoration: BoxDecoration(
        border: Border(
            bottom: BorderSide(
                color: Theme.of(context).dividerColor.withValues(alpha: 0.35))),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 22),
      child: Row(
        children: [
          IconButton(
            onPressed: onToggleSidebar,
            icon: Icon(
                isSidebarCollapsed
                    ? Icons.view_sidebar_outlined
                    : Icons.menu_open,
                size: 22),
            tooltip: isSidebarCollapsed
                ? AppLocalizations.of(context).t('expandSidebar')
                : AppLocalizations.of(context).t('collapseSidebar'),
            style: IconButton.styleFrom(
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10)),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          ),
          const Spacer(),
          IconButton(
            onPressed: onSettings,
            icon: const Icon(Icons.settings_outlined, size: 22),
            tooltip: 'Settings',
            style: IconButton.styleFrom(
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10))),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.l10n, required this.onSuggestion});

  final AppLocalizations l10n;
  final ValueChanged<String> onSuggestion;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const _CloudLogo(size: 112),
              const SizedBox(height: 24),
              Text(
                l10n.t('emptyTitle'),
                textAlign: TextAlign.center,
                style: textTheme.headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 10),
              Text(
                l10n.t('emptyHint'),
                textAlign: TextAlign.center,
                style: textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    height: 1.55),
              ),
              const SizedBox(height: 24),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                alignment: WrapAlignment.center,
                children: [
                  for (final key in [
                    'suggestion1',
                    'suggestion2',
                    'suggestion3'
                  ])
                    ActionChip(
                      label: Text(l10n.t(key)),
                      onPressed: () => onSuggestion(l10n.t(key)),
                      side: BorderSide(
                          color: Theme.of(context)
                              .dividerColor
                              .withValues(alpha: 0.5)),
                      backgroundColor: Theme.of(context)
                          .colorScheme
                          .surface
                          .withValues(alpha: 0.9),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChatBackground extends StatelessWidget {
  const _ChatBackground({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _DottedBackgroundPainter(
        color: Theme.of(context).brightness == Brightness.dark
            ? Colors.white.withValues(alpha: 0.035)
            : const Color(0xFF111827).withValues(alpha: 0.045),
      ),
      child: child,
    );
  }
}

class _DottedBackgroundPainter extends CustomPainter {
  const _DottedBackgroundPainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color;
    const gap = 18.0;
    for (var x = 0.0; x < size.width; x += gap) {
      for (var y = 0.0; y < size.height; y += gap) {
        canvas.drawCircle(Offset(x, y), 0.65, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DottedBackgroundPainter oldDelegate) =>
      oldDelegate.color != color;
}

class _CloudLogo extends StatelessWidget {
  const _CloudLogo({this.size = 48});

  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size * 0.58,
      child: Stack(
        alignment: Alignment.bottomCenter,
        children: [
          _LogoBubble(size: size * 0.36, left: size * 0.1, bottom: size * 0.02),
          _LogoBubble(size: size * 0.58, left: size * 0.33, bottom: 0),
          _LogoBubble(
              size: size * 0.34, left: size * 0.68, bottom: size * 0.03),
        ],
      ),
    );
  }
}

class _LogoBubble extends StatelessWidget {
  const _LogoBubble(
      {required this.size, required this.left, required this.bottom});

  final double size;
  final double left;
  final double bottom;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      left: left,
      bottom: bottom,
      child: Container(
        width: size,
        height: size,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFFFD09A), Color(0xFFF58235)],
          ),
        ),
      ),
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({
    required this.sessions,
    required this.currentSessionId,
    required this.user,
    required this.onNew,
    required this.onSelect,
    required this.onSettings,
    required this.onEditProfile,
    required this.onLogout,
  });

  final List<ChatSession> sessions;
  final String? currentSessionId;
  final UserAccount? user;
  final VoidCallback onNew;
  final ValueChanged<String> onSelect;
  final VoidCallback onSettings;
  final VoidCallback onEditProfile;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Container(
      width: 286,
      decoration: BoxDecoration(
        color: Theme.of(context).brightness == Brightness.dark
            ? const Color(0xFF0B1220)
            : Colors.white,
        border: Border(
            right: BorderSide(
                color: Theme.of(context).dividerColor.withValues(alpha: 0.35))),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 12),
            child: Row(
              children: [
                const _CloudLogo(size: 38),
                const SizedBox(width: 10),
                Text(
                  'Aether',
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 10, 18),
            child: FilledButton.tonalIcon(
              onPressed: onNew,
              icon: const Icon(Icons.add, size: 20),
              label: Text(l10n.t('newChat')),
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(44),
                alignment: Alignment.centerLeft,
                foregroundColor: const Color(0xFF3978FF),
                backgroundColor: const Color(0xFFEAF1FF),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                l10n.t('conversations'),
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: sessions.isEmpty
                ? Padding(
                    padding: const EdgeInsets.fromLTRB(22, 10, 22, 0),
                    child: Align(
                      alignment: Alignment.topLeft,
                      child: Text(
                        l10n.t('noConversations'),
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                      ),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    itemCount: sessions.length,
                    itemBuilder: (context, index) {
                      final session = sessions[index];
                      final selected = session.id == currentSessionId;
                      return ListTile(
                        dense: true,
                        selected: selected,
                        selectedTileColor: const Color(0xFFEAF1FF),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10)),
                        leading: Icon(
                            session.isFavorite
                                ? Icons.star
                                : Icons.chat_bubble_outline,
                            size: 18),
                        title: Text(session.title,
                            maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: session.preview.isEmpty
                            ? null
                            : Text(session.preview,
                                maxLines: 1, overflow: TextOverflow.ellipsis),
                        onTap: () => onSelect(session.id),
                      );
                    },
                  ),
          ),
          _UserMenuCard(
            user: user,
            onSettings: onSettings,
            onEditProfile: onEditProfile,
            onLogout: onLogout,
          ),
        ],
      ),
    );
  }
}

class _UserMenuCard extends StatelessWidget {
  const _UserMenuCard({
    required this.user,
    required this.onSettings,
    required this.onEditProfile,
    required this.onLogout,
  });

  final UserAccount? user;
  final VoidCallback onSettings;
  final VoidCallback onEditProfile;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 10, 10, 14),
      child: PopupMenuButton<String>(
        tooltip: l10n.t('account'),
        offset: const Offset(0, -8),
        position: PopupMenuPosition.over,
        onSelected: (value) {
          switch (value) {
            case 'settings':
              onSettings();
              break;
            case 'profile':
              onEditProfile();
              break;
            case 'logout':
              onLogout();
              break;
          }
        },
        itemBuilder: (context) => [
          PopupMenuItem(
            value: 'profile',
            child: ListTile(
              dense: true,
              leading: const Icon(Icons.person_outline),
              title: Text(l10n.t('editProfile')),
            ),
          ),
          PopupMenuItem(
            value: 'settings',
            child: ListTile(
              dense: true,
              leading: const Icon(Icons.settings_outlined),
              title: Text(l10n.t('settings')),
            ),
          ),
          const PopupMenuDivider(),
          PopupMenuItem(
            value: 'logout',
            child: ListTile(
              dense: true,
              leading: const Icon(Icons.logout),
              title: Text(l10n.t('logout')),
            ),
          ),
        ],
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: Theme.of(context).brightness == Brightness.dark
                ? const Color(0xFF111827)
                : const Color(0xFFF8FAFC),
            border: Border.all(
                color: Theme.of(context).dividerColor.withValues(alpha: 0.35)),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              _UserAvatar(user: user, radius: 18),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      user?.label ?? '',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context)
                          .textTheme
                          .bodyMedium
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    if (user?.email?.isNotEmpty == true)
                      Text(
                        user!.email!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                      ),
                  ],
                ),
              ),
              const Icon(Icons.more_horiz, size: 18),
            ],
          ),
        ),
      ),
    );
  }
}

class _UserAvatar extends StatelessWidget {
  const _UserAvatar({required this.user, this.radius = 18});

  final UserAccount? user;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final data = user?.avatarData;
    if (data != null && data.contains(',')) {
      try {
        return CircleAvatar(
          radius: radius,
          backgroundImage: MemoryImage(base64Decode(data.split(',').last)),
        );
      } catch (_) {
        // Fall through to initials.
      }
    }
    final label = user?.label.trim();
    final initial =
        label == null || label.isEmpty ? 'V' : label.characters.first;
    return CircleAvatar(
      radius: radius,
      backgroundColor: const Color(0xFFEAF1FF),
      child: Text(
        initial,
        style: const TextStyle(
            color: Color(0xFF3978FF), fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _ProfileDialog extends StatefulWidget {
  const _ProfileDialog({required this.user, required this.onSave});

  final UserAccount? user;
  final Future<void> Function({
    required String username,
    required String displayName,
    String? avatarData,
  }) onSave;

  @override
  State<_ProfileDialog> createState() => _ProfileDialogState();
}

class _ProfileDialogState extends State<_ProfileDialog> {
  late final TextEditingController _usernameController;
  late final TextEditingController _displayNameController;
  String? _avatarData;
  String? _error;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _usernameController =
        TextEditingController(text: widget.user?.username ?? '');
    _displayNameController = TextEditingController(
        text: widget.user?.displayName ?? widget.user?.username ?? '');
    _avatarData = widget.user?.avatarData;
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _displayNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(l10n.t('editProfile')),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            GestureDetector(
              onTap: _pickAvatar,
              child: Stack(
                alignment: Alignment.bottomRight,
                children: [
                  _PreviewAvatar(
                      avatarData: _avatarData,
                      label: _displayNameController.text,
                      radius: 38),
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primary,
                      shape: BoxShape.circle,
                    ),
                    child:
                        const Icon(Icons.edit, color: Colors.white, size: 14),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _pickAvatar,
              icon: const Icon(Icons.image_outlined),
              label: Text(l10n.t('changeAvatar')),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _usernameController,
              decoration: InputDecoration(labelText: l10n.t('username')),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _displayNameController,
              decoration: InputDecoration(labelText: l10n.t('displayName')),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: Text(_error!,
                    style:
                        TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            ],
          ],
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

  Future<void> _pickAvatar() async {
    final result = await FilePicker.platform
        .pickFiles(type: FileType.image, allowMultiple: false, withData: true);
    if (result == null || result.files.isEmpty) return;
    final file = result.files.first;
    final bytes = file.bytes;
    if (bytes == null) return;
    setState(() {
      _avatarData =
          'data:${_mimeFromName(file.name)};base64,${base64Encode(bytes)}';
    });
  }

  String _mimeFromName(String name) {
    final lower = name.toLowerCase();
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
    if (lower.endsWith('.webp')) return 'image/webp';
    return 'image/png';
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.onSave(
        username: _usernameController.text.trim(),
        displayName: _displayNameController.text.trim(),
        avatarData: _avatarData,
      );
      if (mounted) Navigator.of(context).pop();
    } catch (error) {
      setState(() {
        _saving = false;
        _error = error.toString();
      });
    }
  }
}

class _PreviewAvatar extends StatelessWidget {
  const _PreviewAvatar(
      {required this.avatarData, required this.label, required this.radius});

  final String? avatarData;
  final String label;
  final double radius;

  @override
  Widget build(BuildContext context) {
    if (avatarData != null && avatarData!.contains(',')) {
      try {
        return CircleAvatar(
            radius: radius,
            backgroundImage:
                MemoryImage(base64Decode(avatarData!.split(',').last)));
      } catch (_) {
        // Fall through to initials.
      }
    }
    final initial = label.trim().isEmpty ? 'V' : label.trim().characters.first;
    return CircleAvatar(
      radius: radius,
      backgroundColor: const Color(0xFFEAF1FF),
      child: Text(initial,
          style: const TextStyle(
              color: Color(0xFF3978FF), fontWeight: FontWeight.w800)),
    );
  }
}

class _MessageTile extends StatelessWidget {
  const _MessageTile({required this.message});
  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    final isFunction = message.role == 'function';
    final isAssistant = !isUser && !isFunction;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final maxWidth = (MediaQuery.sizeOf(context).width * 0.62)
        .clamp(360.0, 820.0)
        .toDouble();
    final bg = isUser
        ? (isDark ? const Color(0xFF1F2937) : const Color(0xFFF3F4F6))
        : isFunction
            ? Theme.of(context)
                .colorScheme
                .secondaryContainer
                .withValues(alpha: 0.45)
            : (isDark ? const Color(0xFF111827) : Colors.white);
    final border = isAssistant
        ? Border.all(
            color: isDark ? const Color(0xFF374151) : const Color(0xFFE5E7EB),
          )
        : null;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 8),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: bg,
            border: border,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              if (isAssistant && !isDark)
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.035),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (message.images.isNotEmpty)
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final image in message.images)
                      ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: Image.memory(
                          base64Decode(image.data.split(',').last),
                          width: 120,
                          height: 120,
                          fit: BoxFit.cover,
                        ),
                      ),
                  ],
                ),
              if (isFunction)
                _FunctionEventView(message: message)
              else
                DefaultTextStyle.merge(
                  style: AppFonts.messageStyle(context),
                  child: MessageRenderer(content: message.content),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FunctionEventView extends StatelessWidget {
  const _FunctionEventView({required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final payload = message.toolPayload ?? {};
    final type = (payload['type'] ?? message.content).toString();
    final data = payload['data'];
    final title = switch (type) {
      'tool_call' => '工具调用',
      'tool_result' => '工具结果',
      'ask_for_info_request' => '等待补充信息',
      'confirmation_request' => '等待确认',
      _ => type,
    };
    final subtitle = _subtitle(type, data);
    final detail = data == null
        ? ''
        : const JsonEncoder.withIndent('  ').convert(_jsonSafe(data));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.extension_outlined, size: 16),
            const SizedBox(width: 6),
            Text(
              title,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
          ],
        ),
        if (subtitle.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(subtitle, style: Theme.of(context).textTheme.bodyMedium),
        ],
        if (detail.isNotEmpty) ...[
          const SizedBox(height: 8),
          SelectableText(
            detail,
            style: AppFonts.codeStyle(context).copyWith(fontSize: 12),
          ),
        ],
      ],
    );
  }

  String _subtitle(String type, dynamic data) {
    if (data is! Map) return '';
    final map = Map<String, dynamic>.from(data);
    if (type == 'tool_call') {
      return (map['function_name'] ?? '').toString();
    }
    if (type == 'tool_result') {
      final result = map['result'];
      if (result is Map) {
        final ok = result['ok'] == true ? '成功' : '失败';
        return '${map['function_name'] ?? ''}：$ok';
      }
    }
    if (type == 'ask_for_info_request') {
      final payload = map['payload'];
      if (payload is Map) {
        final meta = payload['meta'];
        if (meta is Map && meta['title'] != null) return meta['title'].toString();
      }
    }
    if (type == 'confirmation_request') {
      final payload = map['payload'];
      if (payload is Map && payload['description'] != null) {
        return payload['description'].toString();
      }
    }
    return '';
  }

  Object? _jsonSafe(Object? value) {
    if (value is Map) {
      return value.map((key, item) => MapEntry(key.toString(), _jsonSafe(item)));
    }
    if (value is Iterable) {
      return value.map(_jsonSafe).toList();
    }
    return value;
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.images,
    required this.isStreaming,
    required this.hint,
    required this.onPickImage,
    required this.onRemoveImage,
    required this.onSend,
  });

  final TextEditingController controller;
  final List<ImageAttachmentData> images;
  final bool isStreaming;
  final String hint;
  final VoidCallback onPickImage;
  final ValueChanged<int> onRemoveImage;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 8, 24, 20),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 880),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: Theme.of(context).brightness == Brightness.dark
                  ? const Color(0xFF111827)
                  : Colors.white,
              border: Border.all(
                  color:
                      Theme.of(context).dividerColor.withValues(alpha: 0.55)),
              borderRadius: BorderRadius.circular(18),
              boxShadow: [
                if (Theme.of(context).brightness == Brightness.light)
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.06),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
              ],
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
              child: Column(
                children: [
                  if (images.isNotEmpty)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(8, 2, 8, 8),
                        child: Wrap(
                          spacing: 8,
                          children: [
                            for (var i = 0; i < images.length; i++)
                              InputChip(
                                label: Text('Image ${i + 1}'),
                                onDeleted: () => onRemoveImage(i),
                              ),
                          ],
                        ),
                      ),
                    ),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      IconButton(
                        onPressed: isStreaming ? null : onPickImage,
                        icon: const Icon(Icons.image_outlined),
                        tooltip: 'Image',
                        style: IconButton.styleFrom(
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10))),
                      ),
                      Expanded(
                        child: TextField(
                          controller: controller,
                          minLines: 1,
                          maxLines: 6,
                          decoration: InputDecoration(
                            hintText: hint,
                            filled: false,
                            border: InputBorder.none,
                            enabledBorder: InputBorder.none,
                            focusedBorder: InputBorder.none,
                          ),
                          onSubmitted: (_) {
                            if (!isStreaming) onSend();
                          },
                        ),
                      ),
                      const SizedBox(width: 6),
                      IconButton.filled(
                        onPressed: isStreaming ? null : onSend,
                        icon: isStreaming
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.arrow_upward),
                        style: IconButton.styleFrom(
                          backgroundColor: const Color(0xFF111827),
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: Theme.of(context)
                              .colorScheme
                              .surfaceContainerHighest,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14)),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
