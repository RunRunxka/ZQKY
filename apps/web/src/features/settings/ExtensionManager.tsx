'use client';
import { useEffect, useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import {
  readExtensions,
  removeExtension,
  saveExtension,
  subscribeExtensions,
  type ExtensionEntry,
  type ExtensionKind,
} from '@/services/extension-catalog';
export function ExtensionManager({ kind }: { kind: ExtensionKind }) {
  const [items, setItems] = useState<ExtensionEntry[]>([]);
  const [query, setQuery] = useState('');
  const [editor, setEditor] = useState<ExtensionEntry | null>(null);
  const [notice, setNotice] = useState('');
  const [removing, setRemoving] = useState<ExtensionEntry | null>(null);
  useEffect(() => {
    const update = () => {
      try {
        setItems(readExtensions());
      } catch (error) {
        setNotice(String(error));
      }
    };
    update();
    return subscribeExtensions(update);
  }, []);
  const label = kind === 'mcp' ? 'MCP' : 'Skill';
  function perform(action: () => void) {
    try {
      action();
      setNotice('已保存到本机模拟目录，未调用真实服务。');
      return true;
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '无法保存，请检查浏览器存储。');
      return false;
    }
  }
  return (
    <div className="extension-manager">
      <p className="settings-hint">
        模拟模式 · 配置仅用于交互演示，未安装或连接真实扩展。请勿填写密钥。
      </p>
      <div className="settings-toolbar">
        <input
          aria-label={`搜索 ${label}`}
          placeholder="搜索名称或描述"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button
          onClick={() =>
            setEditor({
              id: crypto.randomUUID(),
              kind,
              name: '',
              description: '',
              content: '',
              enabled: false,
            })
          }
        >
          添加 {label}
        </button>
      </div>
      {!items.some((item) => item.kind === kind) && (
        <p className="settings-empty">还没有{label}。添加一个本地演示配置开始体验。</p>
      )}
      {items
        .filter(
          (item) =>
            item.kind === kind &&
            `${item.name} ${item.description}`.toLowerCase().includes(query.toLowerCase()),
        )
        .map((item) => (
          <article className="extension-card" key={item.id}>
            <div>
              <strong>{item.name}</strong>
              <p>{item.description || '暂无描述'}</p>
            </div>
            <div className="settings-toolbar">
              <button
                role="switch"
                aria-checked={item.enabled}
                aria-label={`启用 ${item.name}`}
                onClick={() => perform(() => saveExtension({ ...item, enabled: !item.enabled }))}
              >
                {item.enabled ? '演示已启用' : '未启用'}
              </button>
              <button onClick={() => setEditor({ ...item })}>详情与编辑</button>
              {kind === 'mcp' && (
                <button
                  onClick={() =>
                    setNotice(`模拟检测：${item.name} 的演示配置可读取；未进行网络连接测试。`)
                  }
                >
                  模拟检测
                </button>
              )}
              <button onClick={() => setRemoving(item)}>删除</button>
            </div>
          </article>
        ))}
      <p role="status">{notice}</p>
      {editor && (
        <Modal title={`${label} 配置（模拟）`} onClose={() => setEditor(null)}>
          <form
            className="settings-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (perform(() => saveExtension({ ...editor, name: editor.name.trim() })))
                setEditor(null);
            }}
          >
            <label>
              名称
              <input
                required
                maxLength={80}
                value={editor.name}
                onChange={(e) => setEditor({ ...editor, name: e.target.value })}
              />
            </label>
            <label>
              描述
              <input
                value={editor.description}
                onChange={(e) => setEditor({ ...editor, description: e.target.value })}
              />
            </label>
            <label>
              {kind === 'skill' ? '技能说明（Markdown）' : '服务说明（不含凭证）'}
              <textarea
                rows={8}
                value={editor.content}
                onChange={(e) => setEditor({ ...editor, content: e.target.value })}
              />
            </label>
            <button type="submit">保存模拟配置</button>
            <p role="status">{notice}</p>
          </form>
        </Modal>
      )}
      {removing && (
        <Modal title="删除模拟配置" onClose={() => setRemoving(null)}>
          <p>删除“{removing.name}”？</p>
          <button
            onClick={() => {
              if (perform(() => removeExtension(removing.id))) setRemoving(null);
            }}
          >
            确认删除
          </button>
        </Modal>
      )}
    </div>
  );
}
