import styles from './Markdown.module.css'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Raw HTML is not rendered: answers and plans contain model and web content.
export function Markdown({ children }: { children: string }) {
  return (
    <div className={styles["markdown"]}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
