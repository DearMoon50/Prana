import 'dart:math';
import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme.dart';

class WaterWaveCircle extends StatefulWidget {
  final int score;
  final double size;

  const WaterWaveCircle({
    super.key,
    required this.score,
    this.size = 150.0,
  });

  @override
  State<WaterWaveCircle> createState() => _WaterWaveCircleState();
}

class _WaterWaveCircleState extends State<WaterWaveCircle>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fillPercentage = widget.score / 100.0;

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Container(
          width: widget.size,
          height: widget.size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: Colors.blue.shade500.withValues(alpha: 0.25),
                blurRadius: 20,
                spreadRadius: 4,
              ),
              BoxShadow(
                color: Colors.cyan.shade300.withValues(alpha: 0.1),
                blurRadius: 40,
                spreadRadius: 2,
              )
            ],
          ),
          child: CustomPaint(
            painter: _WaterWavePainter(
              wavePhase: _controller.value * 2 * pi,
              fillLevel: fillPercentage,
            ),
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '${widget.score}',
                    style: const TextStyle(
                      fontSize: 38,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      letterSpacing: -1,
                      shadows: [
                        Shadow(
                          color: Colors.black45,
                          offset: Offset(0, 2),
                          blurRadius: 6,
                        ),
                      ],
                    ),
                  ),
                  Container(
                    margin: const EdgeInsets.only(top: 2),
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.black26,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Text(
                      'CCRI SCORE',
                      style: TextStyle(
                        fontSize: 9,
                        color: Colors.white70,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _WaterWavePainter extends CustomPainter {
  final double wavePhase;
  final double fillLevel;

  _WaterWavePainter({
    required this.wavePhase,
    required this.fillLevel,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final double radius = size.width / 2;
    final center = Offset(radius, radius);

    // 1. Draw premium glassmorphic background disc
    final bgPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          Colors.white.withValues(alpha: 0.08),
          Colors.white.withValues(alpha: 0.02),
        ],
      ).createShader(Rect.fromCircle(center: center, radius: radius))
      ..style = PaintingStyle.fill;
    canvas.drawCircle(center, radius, bgPaint);

    // 2. Draw circular track for progress
    final trackPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.1)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6.0;
    canvas.drawCircle(center, radius - 6, trackPaint);

    // 3. Draw circular neon progress ring based on fill level
    if (fillLevel > 0) {
      final progressPaint = Paint()
        ..shader = SweepGradient(
          colors: [
            Colors.blue.shade600,
            Colors.cyan.shade400,
            Colors.blue.shade600,
          ],
          transform: const GradientRotation(-pi / 2),
        ).createShader(Rect.fromCircle(center: center, radius: radius - 6))
        ..style = PaintingStyle.stroke
        ..strokeWidth = 6.0
        ..strokeCap = StrokeCap.round;

      // Draw progress arc
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius - 6),
        -pi / 2,
        2 * pi * fillLevel,
        false,
        progressPaint,
      );
    }

    // Clip the canvas for waves inside the inner circle (leaving space for outer ring)
    final clipPath = Path()
      ..addOval(Rect.fromCircle(center: center, radius: radius - 10));
    canvas.save();
    canvas.clipPath(clipPath);

    // 4. Draw wave paths with premium shaders
    final wavePath1 = Path();
    final wavePath2 = Path();

    final double waveHeight = 6.0;
    final double waveFrequency = 1.2;
    final double waterHeight = size.height * (1.0 - fillLevel);

    wavePath1.moveTo(0, size.height);
    wavePath2.moveTo(0, size.height);

    for (double x = 0; x <= size.width; x++) {
      final double y1 = waterHeight + sin(x / size.width * 2 * pi * waveFrequency + wavePhase) * waveHeight;
      wavePath1.lineTo(x, y1);

      final double y2 = waterHeight + cos(x / size.width * 2 * pi * waveFrequency - wavePhase) * waveHeight;
      wavePath2.lineTo(x, y2);
    }

    wavePath1.lineTo(size.width, size.height);
    wavePath1.close();
    wavePath2.lineTo(size.width, size.height);
    wavePath2.close();

    // Shaders for the waves
    final waveGradient1 = LinearGradient(
      begin: Alignment.bottomCenter,
      end: Alignment.topCenter,
      colors: [
        Colors.blue.shade900.withValues(alpha: 0.85),
        Colors.cyan.shade400.withValues(alpha: 0.65),
      ],
    ).createShader(Rect.fromCircle(center: center, radius: radius));

    final waveGradient2 = LinearGradient(
      begin: Alignment.bottomCenter,
      end: Alignment.topCenter,
      colors: [
        Colors.blue.shade900.withValues(alpha: 0.4),
        Colors.cyan.shade600.withValues(alpha: 0.3),
      ],
    ).createShader(Rect.fromCircle(center: center, radius: radius));

    // Draw deep wave first
    canvas.drawPath(wavePath2, Paint()..shader = waveGradient2..style = PaintingStyle.fill);

    // Draw front wave
    canvas.drawPath(wavePath1, Paint()..shader = waveGradient1..style = PaintingStyle.fill);

    canvas.restore();

    // 5. Draw inner glass rim highlights
    final innerRimPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.15)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    canvas.drawCircle(center, radius - 10, innerRimPaint);
  }

  @override
  bool shouldRepaint(covariant _WaterWavePainter oldDelegate) {
    return oldDelegate.wavePhase != wavePhase || oldDelegate.fillLevel != fillLevel;
  }
}
