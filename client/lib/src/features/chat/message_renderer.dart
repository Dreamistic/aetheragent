import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_math_fork/flutter_math.dart';

import '../../core/app_fonts.dart';

class MessageRenderer extends StatelessWidget {
  const MessageRenderer({super.key, required this.content});

  final String content;

  @override
  Widget build(BuildContext context) {
    final bubbles = splitBubbles(content);
    if (bubbles.length > 1) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final bubble in bubbles)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _MarkdownMath(content: bubble),
            ),
        ],
      );
    }
    return _MarkdownMath(content: content);
  }
}

List<String> splitBubbles(String raw) {
  final regex = RegExp(r'<bubble>([\s\S]*?)<\/bubble>', caseSensitive: false);
  final matches = regex.allMatches(raw).toList();
  if (matches.isEmpty) return [raw];
  final result = <String>[];
  var cursor = 0;
  for (final match in matches) {
    final before = raw.substring(cursor, match.start).trim();
    if (before.isNotEmpty) result.add(before);
    final bubble = match.group(1)?.trim();
    if (bubble != null && bubble.isNotEmpty) result.add(bubble);
    cursor = match.end;
  }
  final after = raw.substring(cursor).trim();
  if (after.isNotEmpty) result.add(after);
  return result.isEmpty ? [raw] : result;
}

class _MarkdownMath extends StatelessWidget {
  const _MarkdownMath({required this.content});

  final String content;

  @override
  Widget build(BuildContext context) {
    final parts = _splitDisplayMath(content);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final part in parts)
          if (part.isMath)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Math.tex(part.text,
                    textStyle: AppFonts.messageStyle(context)),
              ),
            )
          else
            MarkdownBody(
              data: part.text,
              selectable: true,
              styleSheet:
                  MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                p: AppFonts.messageStyle(context),
                listBullet: AppFonts.messageStyle(context),
                code: AppFonts.codeStyle(context),
                codeblockDecoration: BoxDecoration(
                  color: Theme.of(context)
                      .colorScheme
                      .surfaceContainerHighest
                      .withValues(alpha: 0.55),
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
      ],
    );
  }
}

class _Part {
  const _Part(this.text, this.isMath);
  final String text;
  final bool isMath;
}

List<_Part> _splitDisplayMath(String text) {
  final parts = <_Part>[];
  final regex = RegExp(r'\$\$([\s\S]*?)\$\$');
  var cursor = 0;
  for (final match in regex.allMatches(text)) {
    final before = text.substring(cursor, match.start);
    if (before.trim().isNotEmpty) parts.add(_Part(before, false));
    final formula = match.group(1);
    if (formula != null && formula.trim().isNotEmpty) {
      parts.add(_Part(formula.trim(), true));
    }
    cursor = match.end;
  }
  final after = text.substring(cursor);
  if (after.trim().isNotEmpty) parts.add(_Part(after, false));
  return parts.isEmpty ? [_Part(text, false)] : parts;
}
