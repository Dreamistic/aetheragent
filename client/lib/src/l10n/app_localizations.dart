import 'package:flutter/widgets.dart';

class LocaleParser {
  static Locale parse(String value) {
    if (value == 'zh-Hant') {
      return const Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant');
    }
    if (value == 'zh-Hans') {
      return const Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hans');
    }
    return const Locale('en');
  }
}

class AppLocalizations {
  AppLocalizations(this.locale);

  final Locale locale;

  static const supportedLocales = [
    Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hans'),
    Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant'),
    Locale('en'),
  ];

  static const delegate = _Delegate();

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  String get tag {
    if (locale.scriptCode == 'Hant') return 'zh-Hant';
    if (locale.languageCode == 'zh') return 'zh-Hans';
    return 'en';
  }

  String t(String key) =>
      (_strings[tag] ?? _strings['en']!)[key] ?? _strings['en']![key] ?? key;
}

class _Delegate extends LocalizationsDelegate<AppLocalizations> {
  const _Delegate();

  @override
  bool isSupported(Locale locale) =>
      locale.languageCode == 'zh' || locale.languageCode == 'en';

  @override
  Future<AppLocalizations> load(Locale locale) async =>
      AppLocalizations(locale);

  @override
  bool shouldReload(covariant LocalizationsDelegate<AppLocalizations> old) =>
      false;
}

const _strings = {
  'zh-Hans': {
    'login': '登录',
    'register': '注册',
    'username': '用户名',
    'emailOptional': '邮箱（可选）',
    'password': '密码',
    'usernameRequired': '请输入用户名或邮箱',
    'passwordRequired': '请输入密码',
    'passwordTooShort': '密码至少需要 6 个字符',
    'newChat': '新建会话',
    'chatTitle': '新对话',
    'conversations': '对话',
    'noConversations': '还没有对话',
    'settings': '设置',
    'account': '账户',
    'profile': '个人资料',
    'editProfile': '编辑资料',
    'displayName': '显示名',
    'changeAvatar': '更换头像',
    'collapseSidebar': '折叠侧栏',
    'expandSidebar': '展开侧栏',
    'tools': '工具',
    'skills': 'Skills',
    'noSkills': '还没有加载 Skills',
    'enabled': '启用',
    'mcpServers': 'MCP Server',
    'addMcpServer': '添加 MCP Server',
    'editMcpServer': '编辑 MCP Server',
    'mcpName': '名称',
    'mcpUrl': 'MCP HTTP/SSE 地址',
    'mcpCommand': 'MCP stdio 命令',
    'mcpArgs': 'MCP stdio 参数 JSON',
    'mcpHeaders': '请求头 JSON（可选）',
    'mcpTransport': '传输方式',
    'mcpTimeout': '超时秒数',
    'mcpTest': '测试工具',
    'mcpNoServers': '还没有自定义 MCP Server',
    'mcpToolCount': '可用工具',
    'save': '保存',
    'delete': '删除',
    'cancel': '取消',
    'send': '发送',
    'messageHint': '给 Aether 发送消息',
    'emptyTitle': '今天想做点什么？',
    'emptyHint': '可以直接提问、写作、分析资料，或让 Agent 调用已启用工具。',
    'suggestion1': '今天我该从哪件事开始？',
    'suggestion2': '帮我梳理一下最近的进展',
    'suggestion3': '帮我把一个想法讲清楚',
    'language': '语言',
    'theme': '主题',
    'light': '浅色',
    'dark': '深色',
    'system': '跟随系统',
    'apiBase': '后端地址',
    'contextSwitch': 'AI 自动整理上下文',
    'logout': '退出登录',
  },
  'zh-Hant': {
    'login': '登入',
    'register': '註冊',
    'username': '使用者名稱',
    'emailOptional': '信箱（可選）',
    'password': '密碼',
    'usernameRequired': '請輸入使用者名稱或信箱',
    'passwordRequired': '請輸入密碼',
    'passwordTooShort': '密碼至少需要 6 個字元',
    'newChat': '新增會話',
    'chatTitle': '新對話',
    'conversations': '對話',
    'noConversations': '還沒有對話',
    'settings': '設定',
    'account': '帳戶',
    'profile': '個人資料',
    'editProfile': '編輯資料',
    'displayName': '顯示名稱',
    'changeAvatar': '更換頭像',
    'collapseSidebar': '摺疊側欄',
    'expandSidebar': '展開側欄',
    'tools': '工具',
    'skills': 'Skills',
    'noSkills': '尚未載入 Skills',
    'enabled': '啟用',
    'mcpServers': 'MCP Server',
    'addMcpServer': '新增 MCP Server',
    'editMcpServer': '編輯 MCP Server',
    'mcpName': '名稱',
    'mcpUrl': 'MCP HTTP/SSE 位址',
    'mcpCommand': 'MCP stdio 命令',
    'mcpArgs': 'MCP stdio 參數 JSON',
    'mcpHeaders': '請求標頭 JSON（可選）',
    'mcpTransport': '傳輸方式',
    'mcpTimeout': '逾時秒數',
    'mcpTest': '測試工具',
    'mcpNoServers': '尚未自訂 MCP Server',
    'mcpToolCount': '可用工具',
    'save': '儲存',
    'delete': '刪除',
    'cancel': '取消',
    'send': '傳送',
    'messageHint': '傳送訊息給 Aether',
    'emptyTitle': '今天想做點什麼？',
    'emptyHint': '可以直接提問、寫作、分析資料，或讓 Agent 呼叫已啟用工具。',
    'suggestion1': '今天我該從哪件事開始？',
    'suggestion2': '幫我梳理一下最近的進展',
    'suggestion3': '幫我把一個想法講清楚',
    'language': '語言',
    'theme': '主題',
    'light': '淺色',
    'dark': '深色',
    'system': '跟隨系統',
    'apiBase': '後端位址',
    'contextSwitch': 'AI 自動整理上下文',
    'logout': '登出',
  },
  'en': {
    'login': 'Log in',
    'register': 'Register',
    'username': 'Username',
    'emailOptional': 'Email (optional)',
    'password': 'Password',
    'usernameRequired': 'Enter your username or email',
    'passwordRequired': 'Enter your password',
    'passwordTooShort': 'Password must be at least 6 characters',
    'newChat': 'New chat',
    'chatTitle': 'New chat',
    'conversations': 'Chats',
    'noConversations': 'No conversations yet',
    'settings': 'Settings',
    'account': 'Account',
    'profile': 'Profile',
    'editProfile': 'Edit profile',
    'displayName': 'Display name',
    'changeAvatar': 'Change avatar',
    'collapseSidebar': 'Collapse sidebar',
    'expandSidebar': 'Expand sidebar',
    'tools': 'Tools',
    'skills': 'Skills',
    'noSkills': 'No skills loaded',
    'enabled': 'Enabled',
    'mcpServers': 'MCP Servers',
    'addMcpServer': 'Add MCP Server',
    'editMcpServer': 'Edit MCP Server',
    'mcpName': 'Name',
    'mcpUrl': 'MCP HTTP/SSE URL',
    'mcpCommand': 'MCP stdio command',
    'mcpArgs': 'MCP stdio args JSON',
    'mcpHeaders': 'Headers JSON (optional)',
    'mcpTransport': 'Transport',
    'mcpTimeout': 'Timeout seconds',
    'mcpTest': 'Test tools',
    'mcpNoServers': 'No custom MCP servers yet',
    'mcpToolCount': 'Available tools',
    'save': 'Save',
    'delete': 'Delete',
    'cancel': 'Cancel',
    'send': 'Send',
    'messageHint': 'Message Aether',
    'emptyTitle': 'What can I help with?',
    'emptyHint':
        'Ask a question, draft text, analyze material, or let the agent use enabled tools.',
    'suggestion1': 'What should I start with today?',
    'suggestion2': 'Help me review recent progress',
    'suggestion3': 'Help me clarify an idea',
    'language': 'Language',
    'theme': 'Theme',
    'light': 'Light',
    'dark': 'Dark',
    'system': 'System',
    'apiBase': 'API base URL',
    'contextSwitch': 'AI context cleanup',
    'logout': 'Log out',
  },
};
