import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:aether_client/main.dart';

void main() {
  testWidgets('renders Aether app shell', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const ProviderScope(child: AetherApp()));
    await tester.pump();

    expect(find.text('Aether'), findsOneWidget);
  });
}
