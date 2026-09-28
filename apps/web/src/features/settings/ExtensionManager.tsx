'use client';
/* 消费 globals.css 单一变量层（R-05）：extension-notice 样式归 settings-extend.css */
import { useEffect, useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import {
  BUILTIN_SKILLS,
  readExtensions,
  removeExtension,
  saveExtension,
  seedBuiltinSkills,
  skillTakesEffect,
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
      setNotice(kind === 'skill' ? '已保存到本机目录。' : '已保存到本机登记，未连接任何服务。');
      return true;
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '无法保存，请检查浏览器存储。');
      return false;
    }
  }
  return (
    <div className="extension-manager">
      {/* 口径与 /capabilities 台账一致：Skill 真实生效于提示词层，MCP 未实现 */}
      {kind === 'skill' ? (
        <p className="settings-hint">
          已启用的技能会随本轮问答发送给模型，作为写作与结构规范；技能只影响生成内容，
          不执行工具、不访问外部服务。说明为空的技能不会生效。请勿填写密钥。
        </p>
      ) : (
        <p className="settings-hint">
          当前未实现 · 这里只能本地登记服务信息，不会连接、检测或执行任何外部服务，
          也不会进入问答请求。请勿填写密钥。
        </p>
      )}
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
        {kind === 'skill' && (
          <button
            onClick={() => {
              let seeded = { added: 0, skipped: 0 };
              if (perform(() => (seeded = seedBuiltinSkills())))
                setNotice(
                  `已载入内置教学技能 ${seeded.added} 个${seeded.skipped ? `，跳过同名 ${seeded.skipped} 个` : ''}（预设共 ${BUILTIN_SKILLS.length} 个）。`,
                );
            }}
          >
            载入内置教学技能
          </button>
        )}
      </div>
      {!items.some((item) => item.kind === kind) && (
        <p className="settings-empty">
          {kind === 'skill'
            ? '还没有技能。可载入内置教学技能，或添加自己的技能。'
            : '还没有 MCP。可添加一条本地登记信息。'}
        </p>
      )}
      {items
        .filter(
          (item) =>
            item.kind === kind &&
            `${item.name} ${item.description}`.toLowerCase().includes(query.toLowerCase()),
        )
        .map((item) => (
          <article className="extension-card" key={item.id}>
            <div className="extension-card-body">
              <strong>{item.name}</strong>
              <p>{item.description || '暂无描述'}</p>
              {kind === 'skill' && !skillTakesEffect(item) && (
                <p className="extension-card-warning">
                  未填写技能说明，本轮不会生效；补充说明后才会发送给模型。
                </p>
              )}
            </div>
            <div className="settings-toolbar">
              <button
                role="switch"
                aria-checked={item.enabled}
                aria-label={`启用 ${item.name}`}
                onClick={() => perform(() => saveExtension({ ...item, enabled: !item.enabled }))}
              >
                {item.enabled ? '已启用' : '未启用'}
              </button>
              <button onClick={() => setEditor({ ...item })}>详情与编辑</button>
              {kind === 'mcp' && (
                <button onClick={() => setNotice('未实现：MCP 不会进行连接或可用性检测。')}>
                  检测状态
                </button>
              )}
              <button onClick={() => setRemoving(item)}>删除</button>
            </div>
          </article>
        ))}
      <p role="status" className="extension-notice">
        {notice}
      </p>
      {editor && (
        <Modal title={`${label} 配置`} onClose={() => setEditor(null)}>
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
            <button type="submit">保存</button>
            <p role="status" className="extension-notice">
              {notice}
            </p>
          </form>
        </Modal>
      )}
      {removing && (
        <Modal title="删除配置" onClose={() => setRemoving(null)}>
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
