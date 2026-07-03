import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:prana/main.dart';

void main() {
  testWidgets('App loads smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: PranaApp()));
    await tester.pumpAndSettle();
    // App should render without crashing
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
