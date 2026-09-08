'use client';
import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import './modal.css';

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="workspace-modal"
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="workspace-modal-body">
        <header>
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭对话框" onClick={onClose}>
            <X size={18} />
          </button>
        </header>
        {children}
      </div>
    </dialog>
  );
}
