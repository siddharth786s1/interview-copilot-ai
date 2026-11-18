'use client';

import React from 'react';

interface StructuredAnswerViewProps {
  text: string;
  streaming?: boolean;
}

/**
 * Renders inline Markdown formatting (**bold** and `inline code`) safely as React nodes.
 */
function renderInline(line: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let keyIdx = 0;

  while ((match = regex.exec(line)) !== null) {
    if (match.index > lastIndex) {
      parts.push(line.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={`b-${keyIdx++}`} className="font-semibold text-zinc-50">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code
          key={`c-${keyIdx++}`}
          className="px-1.5 py-0.5 rounded bg-zinc-800/90 text-emerald-300 font-mono text-[12px] border border-zinc-700/60"
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < line.length) {
    parts.push(line.slice(lastIndex));
  }
  return parts;
}

type Block =
  | { type: 'code'; lang: string; content: string }
  | { type: 'heading'; title: string; inlineBody?: string }
  | { type: 'bullets'; items: string[] }
  | { type: 'numbered'; items: string[] }
  | { type: 'paragraph'; text: string };

const SECTION_HEADING_RE =
  /^(?:#{1,3}\s+|\*\*)([A-Za-z][A-Za-z0-9\s/&+-]{1,40}?)(?:\*\*)?(?:\s*[:—-]\s*(.*))?$/;

const KNOWN_SECTIONS = new Set([
  'direct answer',
  'key points',
  'practical example',
  'quick tip',
  'follow-up tip',
  'follow up tip',
  'summary',
  'steps',
  'approach',
  'complexity',
  'time & space complexity',
  'trade-offs',
  'tradeoffs',
  'architecture',
  'example',
  'best practice',
]);

function parseBlocks(raw: string): Block[] {
  const blocks: Block[] = [];
  const lines = raw.replace(/\r\n/g, '\n').split('\n');
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // Fenced code block
    if (trimmed.startsWith('```')) {
      const lang = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      if (i < lines.length) i++; // consume closing fence
      blocks.push({ type: 'code', lang, content: codeLines.join('\n') });
      continue;
    }

    // Markdown heading (# / ## / ###) or standalone **Section Heading**[: body]
    const headingMatch = trimmed.match(SECTION_HEADING_RE);
    const isHashHeading = trimmed.startsWith('#');
    const isBoldHeading =
      trimmed.startsWith('**') &&
      headingMatch !== null &&
      (KNOWN_SECTIONS.has(headingMatch[1].trim().toLowerCase()) ||
        /^\*\*[^*]{2,40}\*\*:?$/.test(trimmed));

    if (headingMatch && (isHashHeading || isBoldHeading)) {
      blocks.push({
        type: 'heading',
        title: headingMatch[1].trim(),
        inlineBody: headingMatch[2]?.trim() || undefined,
      });
      i++;
      continue;
    }

    // Bullet list
    if (/^[-*•]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*•]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*•]\s+/, ''));
        i++;
      }
      blocks.push({ type: 'bullets', items });
      continue;
    }

    // Numbered list
    if (/^\d+[.)]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+[.)]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+[.)]\s+/, ''));
        i++;
      }
      blocks.push({ type: 'numbered', items });
      continue;
    }

    // Regular paragraph (merge consecutive plain lines)
    const paraLines: string[] = [trimmed];
    i++;
    while (i < lines.length) {
      const next = lines[i].trim();
      if (
        !next ||
        next.startsWith('```') ||
        next.startsWith('#') ||
        /^[-*•]\s+/.test(next) ||
        /^\d+[.)]\s+/.test(next) ||
        /^\*\*[^*]{2,40}\*\*:?(\s|$)/.test(next)
      ) {
        break;
      }
      paraLines.push(next);
      i++;
    }
    blocks.push({ type: 'paragraph', text: paraLines.join(' ') });
  }

  return blocks;
}

function getHeadingAccent(title: string): string {
  const t = title.toLowerCase();
  if (t.includes('direct')) return 'text-emerald-400 border-emerald-500/40 bg-emerald-950/30';
  if (t.includes('key') || t.includes('point') || t.includes('step')) return 'text-sky-400 border-sky-500/40 bg-sky-950/30';
  if (t.includes('example') || t.includes('practical')) return 'text-purple-300 border-purple-500/40 bg-purple-950/30';
  if (t.includes('tip') || t.includes('follow')) return 'text-amber-300 border-amber-500/40 bg-amber-950/30';
  return 'text-emerald-300 border-zinc-700 bg-zinc-800/70';
}

export function StructuredAnswerView({ text, streaming = false }: StructuredAnswerViewProps) {
  const blocks = parseBlocks(text);

  if (blocks.length === 0) {
    return (
      <div className="text-sm text-zinc-100 leading-relaxed whitespace-pre-wrap">
        {text}
        {streaming && (
          <span className="inline-block w-2 h-4 ml-1 bg-emerald-400 animate-pulse align-middle" />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3 text-sm text-zinc-100 leading-relaxed font-sans select-text">
      {blocks.map((block, idx) => {
        if (block.type === 'heading') {
          const accent = getHeadingAccent(block.title);
          return (
            <div key={idx} className="pt-1 first:pt-0 space-y-1.5">
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block text-[11px] font-mono uppercase tracking-wider font-semibold px-2 py-0.5 rounded border ${accent}`}
                >
                  {block.title}
                </span>
              </div>
              {block.inlineBody && (
                <p className="text-sm text-zinc-100 leading-relaxed pl-0.5">
                  {renderInline(block.inlineBody)}
                </p>
              )}
            </div>
          );
        }

        if (block.type === 'bullets') {
          return (
            <ul key={idx} className="space-y-1.5 pl-1">
              {block.items.map((item, j) => (
                <li key={j} className="flex items-start gap-2.5 text-sm text-zinc-200">
                  <span className="mt-2 h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" />
                  <span className="leading-relaxed">{renderInline(item)}</span>
                </li>
              ))}
            </ul>
          );
        }

        if (block.type === 'numbered') {
          return (
            <ol key={idx} className="space-y-1.5 pl-1">
              {block.items.map((item, j) => (
                <li key={j} className="flex items-start gap-2.5 text-sm text-zinc-200">
                  <span className="mt-0.5 text-[11px] font-mono font-semibold text-emerald-400 bg-emerald-950/50 border border-emerald-800/50 rounded px-1.5 py-0.2 shrink-0">
                    {j + 1}
                  </span>
                  <span className="leading-relaxed">{renderInline(item)}</span>
                </li>
              ))}
            </ol>
          );
        }

        if (block.type === 'code') {
          return (
            <div
              key={idx}
              className="rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden"
            >
              {block.lang && (
                <div className="px-3 py-1 bg-zinc-900/90 border-b border-zinc-800 text-[10px] font-mono uppercase text-zinc-400">
                  {block.lang}
                </div>
              )}
              <pre className="p-3 overflow-x-auto text-xs font-mono text-emerald-200 leading-relaxed">
                <code>{block.content}</code>
              </pre>
            </div>
          );
        }

        return (
          <p key={idx} className="text-sm text-zinc-100 leading-relaxed">
            {renderInline(block.text)}
          </p>
        );
      })}
      {streaming && (
        <span className="inline-block w-2 h-4 ml-1 bg-emerald-400 animate-pulse align-middle" />
      )}
    </div>
  );
}
