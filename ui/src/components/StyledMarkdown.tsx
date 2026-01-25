/**
 * Styled Markdown component with proper formatting for reports
 */

import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ReactNode, CSSProperties } from 'react';

// Container styles
const containerStyle: CSSProperties = {
  padding: '1.5rem',
  background: 'var(--pf-v6-global--BackgroundColor--100)',
  borderRadius: '8px',
  border: '1px solid var(--pf-v6-global--BorderColor--100)',
  overflow: 'auto',
  lineHeight: '1.6',
};

// Custom component styles for markdown elements
const markdownComponents = {
  // Headers
  h1: ({ children }: { children?: ReactNode }) => (
    <h1 style={{
      fontSize: '1.5rem',
      fontWeight: 600,
      color: 'var(--pf-v6-global--Color--100)',
      borderBottom: '2px solid var(--pf-v6-global--primary-color--100)',
      paddingBottom: '0.5rem',
      marginBottom: '1rem',
      marginTop: '0',
    }}>{children}</h1>
  ),
  h2: ({ children }: { children?: ReactNode }) => (
    <h2 style={{
      fontSize: '1.25rem',
      fontWeight: 600,
      color: 'var(--pf-v6-global--Color--100)',
      borderBottom: '1px solid var(--pf-v6-global--BorderColor--100)',
      paddingBottom: '0.4rem',
      marginBottom: '0.75rem',
      marginTop: '1.5rem',
    }}>{children}</h2>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h3 style={{
      fontSize: '1.1rem',
      fontWeight: 600,
      color: 'var(--pf-v6-global--Color--200)',
      marginBottom: '0.5rem',
      marginTop: '1.25rem',
    }}>{children}</h3>
  ),

  // Paragraphs
  p: ({ children }: { children?: ReactNode }) => (
    <p style={{
      marginBottom: '0.75rem',
      color: 'var(--pf-v6-global--Color--100)',
    }}>{children}</p>
  ),

  // Strong/Bold
  strong: ({ children }: { children?: ReactNode }) => (
    <strong style={{
      fontWeight: 600,
      color: 'var(--pf-v6-global--Color--100)',
    }}>{children}</strong>
  ),

  // Emphasis/Italic
  em: ({ children }: { children?: ReactNode }) => (
    <em style={{
      fontStyle: 'italic',
      color: 'var(--pf-v6-global--Color--200)',
    }}>{children}</em>
  ),

  // Links
  a: ({ href, children }: { href?: string; children?: ReactNode }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        color: 'var(--pf-v6-global--link--Color)',
        textDecoration: 'none',
        fontWeight: 500,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.textDecoration = 'underline';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.textDecoration = 'none';
      }}
    >
      {children}
    </a>
  ),

  // Unordered lists
  ul: ({ children }: { children?: ReactNode }) => (
    <ul style={{
      marginBottom: '1rem',
      paddingLeft: '1.5rem',
      listStyleType: 'disc',
    }}>{children}</ul>
  ),

  // Ordered lists
  ol: ({ children }: { children?: ReactNode }) => (
    <ol style={{
      marginBottom: '1rem',
      paddingLeft: '1.5rem',
      listStyleType: 'decimal',
    }}>{children}</ol>
  ),

  // List items
  li: ({ children }: { children?: ReactNode }) => (
    <li style={{
      marginBottom: '0.35rem',
      color: 'var(--pf-v6-global--Color--100)',
    }}>{children}</li>
  ),

  // Tables
  table: ({ children }: { children?: ReactNode }) => (
    <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '0.9rem',
        border: '1px solid var(--pf-v6-global--BorderColor--100)',
        borderRadius: '4px',
      }}>{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: ReactNode }) => (
    <thead style={{
      background: 'var(--pf-v6-global--BackgroundColor--200)',
    }}>{children}</thead>
  ),
  tbody: ({ children }: { children?: ReactNode }) => (
    <tbody>{children}</tbody>
  ),
  tr: ({ children }: { children?: ReactNode }) => (
    <tr style={{
      borderBottom: '1px solid var(--pf-v6-global--BorderColor--100)',
    }}>{children}</tr>
  ),
  th: ({ children }: { children?: ReactNode }) => (
    <th style={{
      padding: '0.75rem 1rem',
      textAlign: 'left',
      fontWeight: 600,
      color: 'var(--pf-v6-global--Color--100)',
      borderBottom: '2px solid var(--pf-v6-global--BorderColor--100)',
      whiteSpace: 'nowrap',
    }}>{children}</th>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td style={{
      padding: '0.6rem 1rem',
      color: 'var(--pf-v6-global--Color--100)',
      verticalAlign: 'top',
    }}>{children}</td>
  ),

  // Code blocks
  code: ({ children, className }: { children?: ReactNode; className?: string }) => {
    // Inline code vs code block
    const isBlock = className?.includes('language-');
    if (isBlock) {
      return (
        <code style={{
          display: 'block',
          background: 'var(--pf-v6-global--BackgroundColor--dark-300)',
          color: 'var(--pf-v6-global--Color--light-100)',
          padding: '1rem',
          borderRadius: '4px',
          fontSize: '0.875rem',
          fontFamily: 'var(--pf-v6-global--FontFamily--monospace)',
          overflowX: 'auto',
        }}>{children}</code>
      );
    }
    return (
      <code style={{
        background: 'var(--pf-v6-global--BackgroundColor--200)',
        padding: '0.125rem 0.375rem',
        borderRadius: '3px',
        fontSize: '0.875em',
        fontFamily: 'var(--pf-v6-global--FontFamily--monospace)',
        color: 'var(--pf-v6-global--danger-color--100)',
      }}>{children}</code>
    );
  },

  // Blockquotes
  blockquote: ({ children }: { children?: ReactNode }) => (
    <blockquote style={{
      borderLeft: '4px solid var(--pf-v6-global--primary-color--100)',
      margin: '1rem 0',
      paddingLeft: '1rem',
      color: 'var(--pf-v6-global--Color--200)',
      fontStyle: 'italic',
    }}>{children}</blockquote>
  ),

  // Horizontal rules
  hr: () => (
    <hr style={{
      border: 'none',
      borderTop: '1px solid var(--pf-v6-global--BorderColor--100)',
      margin: '1.5rem 0',
    }} />
  ),
};

interface StyledMarkdownProps {
  children: string;
  maxHeight?: string;
  compact?: boolean;
}

export function StyledMarkdown({ children, maxHeight = '400px', compact = false }: StyledMarkdownProps) {
  const style: CSSProperties = {
    ...containerStyle,
    maxHeight,
    ...(compact ? { padding: '1rem' } : {}),
  };

  return (
    <div style={style}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
      >
        {children}
      </Markdown>
    </div>
  );
}

// Inline markdown for summaries (no container, just formatted text)
export function InlineMarkdown({ children }: { children: string }) {
  return (
    <span style={{ display: 'inline' }}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          ...markdownComponents,
          p: ({ children: c }) => <span>{c}</span>,
        }}
      >
        {children}
      </Markdown>
    </span>
  );
}

export default StyledMarkdown;
