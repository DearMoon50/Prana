import 'package:flutter_test/flutter_test.dart';

import 'package:prana_app/main.dart';

void main() {
  testWidgets('PRANA dashboard renders core controls', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const PranaApp());

    expect(find.text('PRANA'), findsOneWidget);
    expect(find.text('Location'), findsOneWidget);
    expect(find.text('Use GPS'), findsOneWidget);
    expect(find.text('Calculate'), findsOneWidget);
    expect(find.text('Live PRANA results will appear here.'), findsOneWidget);
  });
}
