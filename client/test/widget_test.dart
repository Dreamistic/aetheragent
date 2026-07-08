import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:vaeagent_client/main.dart';

void main() {
  testWidgets('renders VAEAGENT app shell', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const ProviderScope(child: VaeAgentApp()));
    await tester.pump();

    expect(find.text('VAEAGENT'), findsOneWidget);
  });
}
