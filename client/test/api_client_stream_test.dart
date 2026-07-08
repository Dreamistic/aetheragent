import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:vaeagent_client/src/core/api_client.dart';

void main() {
  test('chatStream parses tool events from ndjson', () async {
    final client = MockClient((request) async {
      expect(request.url.path, '/api/chat/stream');
      final lines = [
        {'type': 'trace', 'data': {'trace_id': 'chat_test'}},
        {
          'type': 'tool_call',
          'data': {'function_name': 'create_task', 'arguments': '{}'}
        },
        {
          'type': 'tool_result',
          'data': {
            'function_name': 'create_task',
            'result': {'ok': true}
          }
        },
        {'type': 'final', 'data': 'done'},
        {'type': 'end', 'data': null},
      ].map(jsonEncode).join('\n');
      return http.Response(lines, 200,
          headers: {'content-type': 'application/x-ndjson'});
    });

    final api = ApiClient(baseUrl: 'http://localhost:8000', client: client);
    final events = await api.chatStream(message: 'hi', sessionId: null).toList();
    expect(events.map((event) => event.type), [
      'trace',
      'tool_call',
      'tool_result',
      'final',
      'end',
    ]);
    expect(events[2].data['result']['ok'], true);
  });
}
