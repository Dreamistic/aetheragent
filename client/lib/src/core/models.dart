class UserAccount {
  const UserAccount({
    required this.id,
    required this.username,
    this.displayName,
    this.email,
    this.avatarData,
  });

  final String id;
  final String username;
  final String? displayName;
  final String? email;
  final String? avatarData;

  String get label =>
      (displayName?.trim().isNotEmpty == true ? displayName : username) ??
      username;

  factory UserAccount.fromJson(Map<String, dynamic> json) => UserAccount(
        id: json['id'] as String,
        username: json['username'] as String,
        displayName: json['display_name'] as String?,
        email: json['email'] as String?,
        avatarData: json['avatar_data'] as String?,
      );
}

class ChatSession {
  const ChatSession({
    required this.id,
    required this.title,
    required this.messageCount,
    this.preview = '',
    this.isFavorite = false,
  });

  final String id;
  final String title;
  final int messageCount;
  final String preview;
  final bool isFavorite;

  factory ChatSession.fromJson(Map<String, dynamic> json) => ChatSession(
        id: json['session_id'] as String,
        title: (json['title'] as String?) ?? 'New chat',
        messageCount: (json['message_count'] as num?)?.toInt() ?? 0,
        preview: (json['preview'] as String?) ?? '',
        isFavorite: (json['is_favorite'] as bool?) ?? false,
      );
}

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.createdAt,
    this.route,
    this.images = const [],
    this.toolPayload,
  });

  final String id;
  final String role;
  final String content;
  final DateTime createdAt;
  final String? route;
  final List<ImageAttachmentData> images;
  final Map<String, dynamic>? toolPayload;

  ChatMessage copyWith({String? content, Map<String, dynamic>? toolPayload}) =>
      ChatMessage(
        id: id,
        role: role,
        content: content ?? this.content,
        createdAt: createdAt,
        route: route,
        images: images,
        toolPayload: toolPayload ?? this.toolPayload,
      );

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: json['id'] as String,
        role: json['role'] as String,
        content: (json['content'] as String?) ?? '',
        createdAt: DateTime.tryParse((json['created_at'] as String?) ?? '') ??
            DateTime.now(),
        route: json['route'] as String?,
        images: ((json['images'] as List?) ?? [])
            .whereType<Map>()
            .map((item) =>
                ImageAttachmentData.fromJson(Map<String, dynamic>.from(item)))
            .toList(),
        toolPayload: ((json['meta'] as Map?) ?? {})['tool_payload'] is Map
            ? Map<String, dynamic>.from(
                ((json['meta'] as Map?) ?? {})['tool_payload'] as Map)
            : null,
      );
}

class ImageAttachmentData {
  const ImageAttachmentData({required this.data, required this.mimeType});

  final String data;
  final String mimeType;

  Map<String, dynamic> toJson() => {'data': data, 'mime_type': mimeType};

  factory ImageAttachmentData.fromJson(Map<String, dynamic> json) =>
      ImageAttachmentData(
        data: (json['data'] ?? json['url']) as String,
        mimeType: (json['mime_type'] as String?) ?? 'image/png',
      );
}

class ToolMeta {
  const ToolMeta({
    required this.name,
    required this.description,
    required this.enabled,
    this.source = 'builtin',
    this.serverName,
  });

  final String name;
  final String description;
  final bool enabled;
  final String source;
  final String? serverName;

  factory ToolMeta.fromJson(Map<String, dynamic> json) => ToolMeta(
        name: json['name'] as String,
        description: (json['description'] as String?) ?? '',
        enabled: (json['enabled'] as bool?) ?? true,
        source: (json['source'] as String?) ?? 'builtin',
        serverName: json['server_name'] as String?,
      );
}

class SkillMeta {
  const SkillMeta({
    required this.id,
    required this.name,
    required this.description,
    required this.loaded,
    required this.path,
  });

  final String id;
  final String name;
  final String description;
  final bool loaded;
  final String path;

  factory SkillMeta.fromJson(Map<String, dynamic> json) => SkillMeta(
        id: json['id'] as String,
        name: (json['name'] as String?) ?? json['id'] as String,
        description: (json['description'] as String?) ?? '',
        loaded: (json['loaded'] as bool?) ?? false,
        path: (json['path'] as String?) ?? '',
      );
}

class McpServerConfig {
  const McpServerConfig({
    required this.id,
    required this.name,
    required this.transport,
    this.url,
    this.command,
    this.args = const [],
    this.headers = const {},
    this.enabled = true,
    this.approvalRequired = false,
    this.timeoutSeconds = 30,
    this.lastError,
  });

  final String id;
  final String name;
  final String transport;
  final String? url;
  final String? command;
  final List<String> args;
  final Map<String, String> headers;
  final bool enabled;
  final bool approvalRequired;
  final int timeoutSeconds;
  final String? lastError;

  Map<String, dynamic> toPayload() => {
        'name': name,
        'transport': transport,
        if (url != null && url!.trim().isNotEmpty) 'url': url!.trim(),
        if (command != null && command!.trim().isNotEmpty)
          'command': command!.trim(),
        'args': args,
        'headers': headers,
        'enabled': enabled,
        'approval_required': approvalRequired,
        'timeout_seconds': timeoutSeconds,
      };

  McpServerConfig copyWith({
    String? id,
    String? name,
    String? transport,
    String? url,
    String? command,
    List<String>? args,
    Map<String, String>? headers,
    bool? enabled,
    bool? approvalRequired,
    int? timeoutSeconds,
    String? lastError,
  }) =>
      McpServerConfig(
        id: id ?? this.id,
        name: name ?? this.name,
        transport: transport ?? this.transport,
        url: url ?? this.url,
        command: command ?? this.command,
        args: args ?? this.args,
        headers: headers ?? this.headers,
        enabled: enabled ?? this.enabled,
        approvalRequired: approvalRequired ?? this.approvalRequired,
        timeoutSeconds: timeoutSeconds ?? this.timeoutSeconds,
        lastError: lastError ?? this.lastError,
      );

  factory McpServerConfig.fromJson(Map<String, dynamic> json) =>
      McpServerConfig(
        id: json['id'] as String,
        name: json['name'] as String,
        transport: (json['transport'] as String?) ?? 'streamable_http',
        url: json['url'] as String?,
        command: json['command'] as String?,
        args: ((json['args'] as List?) ?? [])
            .map((item) => item.toString())
            .toList(),
        headers: ((json['headers'] as Map?) ?? {})
            .map((key, value) => MapEntry(key.toString(), value.toString())),
        enabled: (json['enabled'] as bool?) ?? true,
        approvalRequired: (json['approval_required'] as bool?) ?? false,
        timeoutSeconds: (json['timeout_seconds'] as num?)?.toInt() ?? 30,
        lastError: json['last_error'] as String?,
      );
}

class StreamEvent {
  const StreamEvent({required this.type, this.data, this.errorType});

  final String type;
  final dynamic data;
  final String? errorType;

  factory StreamEvent.fromJson(Map<String, dynamic> json) => StreamEvent(
        type: json['type'] as String,
        data: json['data'],
        errorType: json['error_type'] as String?,
      );
}
