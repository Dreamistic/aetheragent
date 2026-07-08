import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

class ApiClient {
  ApiClient({required this.baseUrl, this.accessToken, http.Client? client})
      : _client = client ?? http.Client();

  final String baseUrl;
  final String? accessToken;
  final http.Client _client;

  ApiClient copyWith({String? baseUrl, String? accessToken}) => ApiClient(
        baseUrl: baseUrl ?? this.baseUrl,
        accessToken: accessToken ?? this.accessToken,
        client: _client,
      );

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (accessToken != null) 'Authorization': 'Bearer $accessToken',
      };

  Uri _uri(String path) => Uri.parse('$baseUrl/api$path');

  Future<Map<String, dynamic>> register({
    required String username,
    required String password,
    String? email,
  }) {
    return _jsonPost('/auth/register', {
      'username': username,
      'password': password,
      if (email != null && email.trim().isNotEmpty) 'email': email.trim(),
    });
  }

  Future<Map<String, dynamic>> login(
      {required String usernameOrEmail, required String password}) {
    return _jsonPost('/auth/login',
        {'username_or_email': usernameOrEmail, 'password': password});
  }

  Future<Map<String, dynamic>> me() => _jsonGet('/auth/me');

  Future<Map<String, dynamic>> updateProfile({
    String? username,
    String? displayName,
    String? avatarData,
  }) =>
      _jsonPut('/auth/profile', {
        if (username != null) 'username': username,
        if (displayName != null) 'display_name': displayName,
        if (avatarData != null) 'avatar_data': avatarData,
      });

  Future<Map<String, dynamic>> settings() => _jsonGet('/settings');

  Future<Map<String, dynamic>> updateSettings(Map<String, dynamic> data) =>
      _jsonPut('/settings', data);

  Future<Map<String, dynamic>> sessions() => _jsonGet('/sessions');

  Future<Map<String, dynamic>> currentSession() =>
      _jsonGet('/sessions/current');

  Future<Map<String, dynamic>> newSession() =>
      _jsonPost('/sessions/new', {'auto_summarize': true});

  Future<Map<String, dynamic>> switchSession(String sessionId) =>
      _jsonPost('/sessions/switch', {'session_id': sessionId});

  Future<Map<String, dynamic>> tools() => _jsonGet('/tools');

  Future<Map<String, dynamic>> skills() => _jsonGet('/skills');

  Future<Map<String, dynamic>> logs({int limit = 200}) =>
      _jsonGet('/logs/events?limit=$limit');

  Future<Map<String, dynamic>> toggleTool(String name, bool enabled) =>
      _jsonPost('/tools/toggle', {'name': name, 'enabled': enabled});

  Future<Map<String, dynamic>> mcpServers() => _jsonGet('/mcp/servers');

  Future<Map<String, dynamic>> createMcpServer(McpServerConfig server) =>
      _jsonPost('/mcp/servers', server.toPayload());

  Future<Map<String, dynamic>> updateMcpServer(McpServerConfig server) =>
      _jsonPut('/mcp/servers/${server.id}', server.toPayload());

  Future<Map<String, dynamic>> deleteMcpServer(String id) =>
      _jsonDelete('/mcp/servers/$id');

  Future<Map<String, dynamic>> mcpServerTools(String id) =>
      _jsonGet('/mcp/servers/$id/tools');

  Stream<StreamEvent> chatStream({
    required String message,
    required String? sessionId,
    List<ImageAttachmentData> images = const [],
  }) async* {
    final request = http.Request('POST', _uri('/chat/stream'));
    request.headers.addAll(_headers);
    request.body = jsonEncode({
      'message': message,
      'session_id': sessionId,
      if (images.isNotEmpty)
        'images': images.map((item) => item.toJson()).toList(),
    });
    final response = await _client.send(request);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final body = await response.stream.bytesToString();
      throw ApiException(_friendlyHttpError(response.statusCode, body));
    }
    await for (final line in response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter())) {
      final trimmed = line.trim();
      if (trimmed.isEmpty) continue;
      yield StreamEvent.fromJson(jsonDecode(trimmed) as Map<String, dynamic>);
    }
  }

  Future<Map<String, dynamic>> _jsonGet(String path) async {
    final response = await _client.get(_uri(path), headers: _headers);
    return _decode(response);
  }

  Future<Map<String, dynamic>> _jsonPost(
      String path, Map<String, dynamic> body) async {
    final response = await _client.post(_uri(path),
        headers: _headers, body: jsonEncode(body));
    return _decode(response);
  }

  Future<Map<String, dynamic>> _jsonPut(
      String path, Map<String, dynamic> body) async {
    final response = await _client.put(_uri(path),
        headers: _headers, body: jsonEncode(body));
    return _decode(response);
  }

  Future<Map<String, dynamic>> _jsonDelete(String path) async {
    final response = await _client.delete(_uri(path), headers: _headers);
    return _decode(response);
  }

  Map<String, dynamic> _decode(http.Response response) {
    final text = utf8.decode(response.bodyBytes);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(_friendlyHttpError(response.statusCode, text));
    }
    return jsonDecode(text) as Map<String, dynamic>;
  }

  String _friendlyHttpError(int statusCode, String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map<String, dynamic>) {
        final detail = decoded['detail'];
        if (detail is String) {
          return detail;
        }
        if (detail is List) {
          final messages = detail
              .map((item) {
                if (item is! Map) return item.toString();
                final map = Map<String, dynamic>.from(item);
                final loc = (map['loc'] as List?)?.join('.') ?? '';
                final field = loc.split('.').last;
                final msg = (map['msg'] as String?) ?? 'Invalid value';
                return switch (field) {
                  'username_or_email' => '请输入用户名或邮箱',
                  'username' => '请输入用户名',
                  'password' =>
                    msg.contains('at least 6') ? '密码至少需要 6 个字符' : '请输入密码',
                  'email' => '邮箱格式不正确',
                  _ => msg,
                };
              })
              .toSet()
              .join('\n');
          if (messages.isNotEmpty) return messages;
        }
      }
    } catch (_) {
      // Fall through to the generic HTTP error below.
    }
    return 'HTTP $statusCode: $body';
  }
}

class ApiException implements Exception {
  ApiException(this.message);
  final String message;

  @override
  String toString() => message;
}
