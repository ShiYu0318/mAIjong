import type { HTMLAttributes, ReactNode } from "react";

type Props = HTMLAttributes<HTMLElement> & { title?: ReactNode; action?: ReactNode; as?: "section" | "div" };

/** Glassy card with an optional title row. */
export function Panel({ title, action, as: Tag = "section", className = "", children, ...rest }: Props) {
  return (
    <Tag {...rest} className={`panel p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {title && <h2 className="font-display text-xl font-black tracking-wide">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </Tag>
  );
}
