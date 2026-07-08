import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';
import 'models.dart';

final appControllerProvider =
    StateNotifierProvider<AppController, AppState>((ref) => AppController());

const Object _unchanged = Object();

class AppState {
  const AppState({
    required this.apiBaseUrl,
    this.accessToken,
    this.refreshToken,
    this.user,
    this.locale = 'zh-Hans',
    this.theme = 'light',
    this.currentSessionId,
    this.sessions = const [],
    this.messages = const [],
    this.tools = const [],
    this.skills = const [],
    this.mcpServers = const [],
    this.pendingClientRequest,
    this.contextAutoSwitchEnabled = true,
    this.isLoading = false,
    this.isStreaming = false,
    this.error,
  });

  final String apiBaseUrl;
  final String? accessToken;
  final String? refreshToken;
  final UserAccount? user;
  final String locale;
  final String theme;
  final String? currentSessionId;
  final List<ChatSession> sessions;
  final List<ChatMessage> messages;
  final List<ToolMeta> tools;
  final List<SkillMeta> skills;
  final List<McpServerConfig> mcpServers;
  final Map<String, dynamic>? pendingClientRequest;
  final bool contextAutoSwitchEnabled;
  final bool isLoading;
  final bool isStreaming;
  final String? error;

  bool get isAuthenticated => accessToken != null && user != null;

  ThemeMode get themeMode => switch (theme) {
        'dark' => ThemeMode.dark,
        'system' => ThemeMode.system,
        _ => ThemeMode.light,
      };

  AppState copyWith({
    String? apiBaseUrl,
    String? accessToken,
    String? refreshToken,
    UserAccount? user,
    String? locale,
    String? theme,
    String? currentSessionId,
    List<ChatSession>? sessions,
    List<ChatMessage>? messages,
    List<ToolMeta>? tools,
    List<SkillMeta>? skills,
    List<McpServerConfig>? mcpServers,
    Object? pendingClientRequest = _unchanged,
    bool? contextAutoSwitchEnabled,
    bool? isLoading,
    bool? isStreaming,
    Object? error = _unchanged,
    bool clearAuth = false,
  }) {
    return AppState(
      apiBaseUrl: apiBaseUrl ?? this.apiBaseUrl,
      accessToken: clearAuth ? null : accessToken ?? this.accessToken,
      refreshToken: clearAuth ? null : refreshToken ?? this.refreshToken,
      user: clearAuth ? null : user ?? this.user,
      locale: locale ?? this.locale,
      theme: theme ?? this.theme,
      currentSessionId: currentSessionId ?? this.currentSessionId,
      sessions: sessions ?? this.sessions,
      messages: messages ?? this.messages,
      tools: tools ?? this.tools,
      skills: skills ?? this.skills,
      mcpServers: mcpServers ?? this.mcpServers,
      pendingClientRequest: identical(pendingClientRequest, _unchanged)
          ? this.pendingClientRequest
          : pendingClientRequest as Map<String, dynamic>?,
      contextAutoSwitchEnabled:
          contextAutoSwitchEnabled ?? this.contextAutoSwitchEnabled,
      isLoading: isLoading ?? this.isLoading,
      isStreaming: isStreaming ?? this.isStreaming,
      error: identical(error, _unchanged) ? this.error : error as String?,
    );
  }
}

class AppController extends StateNotifier<AppState> {
  AppController() : super(AppState(apiBaseUrl: _defaultApiBaseUrl())) {
    unawaited(_restore());
  }

  ApiClient get _api =>
      ApiClient(baseUrl: state.apiBaseUrl, accessToken: state.accessToken);

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    final refresh = prefs.getString('refresh_token');
    final baseUrl = prefs.getString('api_base_url') ?? state.apiBaseUrl;
    final locale = prefs.getString('locale') ?? state.locale;
    final theme = prefs.getString('theme') ?? state.theme;
    state = state.copyWith(
        apiBaseUrl: baseUrl,
        accessToken: token,
        refreshToken: refresh,
        locale: locale,
        theme: theme);
    if (token != null) {
      try {
        final me = await _api.me();
        state = state.copyWith(
            user: UserAccount.fromJson(me['user'] as Map<String, dynamic>));
        await bootstrap();
      } catch (_) {
        await logout();
      }
    }
  }

  Future<void> login(String usernameOrEmail, String password) async {
    await _auth(
        () => _api.login(usernameOrEmail: usernameOrEmail, password: password));
  }

  Future<void> register(String username, String password, String? email) async {
    await _auth(() =>
        _api.register(username: username, password: password, email: email));
  }

  Future<void> _auth(Future<Map<String, dynamic>> Function() action) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final result = await action();
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('access_token', result['access_token'] as String);
      await prefs.setString('refresh_token', result['refresh_token'] as String);
      state = state.copyWith(
        accessToken: result['access_token'] as String,
        refreshToken: result['refresh_token'] as String,
        user: UserAccount.fromJson(result['user'] as Map<String, dynamic>),
        isLoading: false,
      );
      await bootstrap();
    } catch (error) {
      state = state.copyWith(isLoading: false, error: error.toString());
    }
  }

  Future<void> bootstrap() async {
    final settings = await _api.settings();
    final rawSettings = settings['settings'] as Map<String, dynamic>;
    final sessions = await _api.sessions();
    final current = await _api.currentSession();
    final tools = await _api.tools();
    final skills = await _api.skills();
    final mcpServers = await _api.mcpServers();
    state = state.copyWith(
      locale: rawSettings['locale'] as String? ?? state.locale,
      theme: rawSettings['theme'] as String? ?? state.theme,
      contextAutoSwitchEnabled:
          rawSettings['context_auto_switch_enabled'] as bool? ??
              state.contextAutoSwitchEnabled,
      currentSessionId: current['session_id'] as String?,
      sessions: ((sessions['sessions'] as List?) ?? [])
          .map((item) => ChatSession.fromJson(item as Map<String, dynamic>))
          .toList(),
      messages: ((current['messages'] as List?) ?? [])
          .map((item) => ChatMessage.fromJson(item as Map<String, dynamic>))
          .toList(),
      tools: ((tools['tools'] as List?) ?? [])
          .map((item) => ToolMeta.fromJson(item as Map<String, dynamic>))
          .toList(),
      skills: ((skills['skills'] as List?) ?? [])
          .map((item) => SkillMeta.fromJson(item as Map<String, dynamic>))
          .toList(),
      mcpServers: ((mcpServers['servers'] as List?) ?? [])
          .map((item) => McpServerConfig.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }

  Future<void> newSession() async {
    final result = await _api.newSession();
    state = state.copyWith(
      currentSessionId: result['session_id'] as String?,
      messages: ((result['messages'] as List?) ?? [])
          .map((item) => ChatMessage.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
    await refreshSessions();
  }

  Future<void> switchSession(String sessionId) async {
    final result = await _api.switchSession(sessionId);
    state = state.copyWith(
      currentSessionId: result['session_id'] as String?,
      messages: ((result['messages'] as List?) ?? [])
          .map((item) => ChatMessage.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
    await refreshSessions();
  }

  Future<void> refreshSessions() async {
    final sessions = await _api.sessions();
    state = state.copyWith(
      sessions: ((sessions['sessions'] as List?) ?? [])
          .map((item) => ChatSession.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }

  Future<void> sendMessage(String text,
      {List<ImageAttachmentData> images = const []}) async {
    if (state.isStreaming || (text.trim().isEmpty && images.isEmpty)) return;
    final userMessage = ChatMessage(
      id: 'local-user-${DateTime.now().microsecondsSinceEpoch}',
      role: 'user',
      content: text,
      createdAt: DateTime.now(),
      images: images,
    );
    final assistantMessage = ChatMessage(
      id: 'stream-${DateTime.now().microsecondsSinceEpoch}',
      role: 'assistant',
      content: '',
      createdAt: DateTime.now(),
    );
    state = state.copyWith(
        messages: [...state.messages, userMessage, assistantMessage],
        isStreaming: true,
        error: null);
    try {
      var streamFailed = false;
      await for (final event in _api.chatStream(
          message: text, sessionId: state.currentSessionId, images: images)) {
        if (event.type == 'api_error' || event.type == 'error') {
          streamFailed = true;
        }
        _handleStreamEvent(event, assistantMessage.id);
      }
      if (streamFailed) {
        await refreshSessions();
        state = state.copyWith(isStreaming: false);
        return;
      }
      await bootstrap();
    } catch (error) {
      state = state.copyWith(isStreaming: false, error: error.toString());
    }
  }

  void _handleStreamEvent(StreamEvent event, String streamId) {
    if (event.type == 'token' && event.data is String) {
      state = state.copyWith(
        messages: [
          for (final message in state.messages)
            if (message.id == streamId)
              message.copyWith(
                  content: message.content + (event.data as String))
            else
              message,
        ],
      );
      return;
    }
    if (event.type == 'tool_call' ||
        event.type == 'tool_result' ||
        event.type == 'ask_for_info_request' ||
        event.type == 'confirmation_request') {
      final isClientRequest = event.type == 'ask_for_info_request' ||
          event.type == 'confirmation_request';
      final request =
          isClientRequest ? {'type': event.type, 'data': event.data} : null;
      final toolMessage = ChatMessage(
        id: 'tool-${DateTime.now().microsecondsSinceEpoch}',
        role: 'function',
        content: event.type,
        createdAt: DateTime.now(),
        toolPayload: {'type': event.type, 'data': event.data},
      );
      state = state.copyWith(
        messages: [...state.messages, toolMessage],
        pendingClientRequest: isClientRequest ? request : _unchanged,
      );
      return;
    }
    if (event.type == 'context_switched' && event.data is Map) {
      final data = Map<String, dynamic>.from(event.data as Map);
      state =
          state.copyWith(currentSessionId: data['new_session_id'] as String?);
      return;
    }
    if (event.type == 'api_error' || event.type == 'error') {
      state = state.copyWith(error: event.data.toString(), isStreaming: false);
      return;
    }
    if (event.type == 'end') {
      state = state.copyWith(isStreaming: false);
    }
  }

  Future<void> updateLocale(String locale) async {
    await _api.updateSettings({'locale': locale});
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('locale', locale);
    state = state.copyWith(locale: locale);
  }

  void clearPendingClientRequest() {
    state = state.copyWith(pendingClientRequest: null);
  }

  Future<void> updateTheme(String theme) async {
    await _api.updateSettings({'theme': theme});
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('theme', theme);
    state = state.copyWith(theme: theme);
  }

  Future<void> updateContextSwitch(bool enabled) async {
    await _api.updateSettings({'context_auto_switch_enabled': enabled});
    state = state.copyWith(contextAutoSwitchEnabled: enabled);
  }

  Future<void> updateApiBaseUrl(String value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_base_url', value);
    state = state.copyWith(apiBaseUrl: value);
  }

  Future<void> toggleTool(String name, bool enabled) async {
    final result = await _api.toggleTool(name, enabled);
    state = state.copyWith(
      tools: ((result['tools'] as List?) ?? [])
          .map((item) => ToolMeta.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }

  Future<void> updateProfile({
    String? username,
    String? displayName,
    String? avatarData,
  }) async {
    final result = await _api.updateProfile(
      username: username,
      displayName: displayName,
      avatarData: avatarData,
    );
    state = state.copyWith(
        user: UserAccount.fromJson(result['user'] as Map<String, dynamic>));
  }

  Future<void> saveMcpServer(McpServerConfig server) async {
    if (server.id.isEmpty) {
      await _api.createMcpServer(server);
    } else {
      await _api.updateMcpServer(server);
    }
    await refreshMcpServers();
    final tools = await _api.tools();
    state = state.copyWith(
      tools: ((tools['tools'] as List?) ?? [])
          .map((item) => ToolMeta.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }

  Future<void> deleteMcpServer(String id) async {
    await _api.deleteMcpServer(id);
    await refreshMcpServers();
    final tools = await _api.tools();
    state = state.copyWith(
      tools: ((tools['tools'] as List?) ?? [])
          .map((item) => ToolMeta.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }

  Future<List<String>> refreshMcpServerTools(String id) async {
    final result = await _api.mcpServerTools(id);
    await refreshMcpServers();
    final tools = ((result['tools'] as List?) ?? [])
        .whereType<Map>()
        .map((item) => (item['name'] ?? '').toString())
        .where((name) => name.isNotEmpty)
        .toList();
    return tools;
  }

  Future<void> refreshMcpServers() async {
    final mcpServers = await _api.mcpServers();
    state = state.copyWith(
      mcpServers: ((mcpServers['servers'] as List?) ?? [])
          .map((item) => McpServerConfig.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
    state = state.copyWith(
      clearAuth: true,
      sessions: [],
      messages: [],
      tools: [],
      skills: [],
      mcpServers: [],
      currentSessionId: '',
      isStreaming: false,
      error: null,
    );
  }

  static String _defaultApiBaseUrl() {
    if (kIsWeb) {
      final origin = Uri.base.origin;
      if (origin.startsWith('http://') || origin.startsWith('https://')) {
        return origin;
      }
    }
    return 'http://127.0.0.1:8000';
  }
}
