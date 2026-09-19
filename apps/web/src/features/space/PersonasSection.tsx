'use client';
import { useCallback, useEffect, useState } from 'react';
import { Eye, Pencil, Sparkles, Trash2, UserPlus } from 'lucide-react';
import { SpaceMain } from './SpaceMain';
import './styles/space-sections.css';
import { Modal } from '@/components/ui/Modal';
import {
  createPersona,
  deletePersona,
  loadDemoPersonas,
  PersonaValidationError,
  readPersonas,
  subscribePersonas,
  updatePersona,
  type PersonaEntry,
} from '@/services/persona-catalog';

type DialogState =
  | { kind: 'view'; persona: PersonaEntry }
  | { kind: 'edit'; persona: PersonaEntry | null }
  | null;

export function PersonasSection() {
  const [personas, setPersonas] = useState<PersonaEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogState>(null);

  const refresh = useCallback(() => {
    try {
      setPersonas(readPersonas());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '角色目录无法读取，原数据未修改。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribePersonas(refresh);
  }, [refresh]);

  function handleLoadDemo() {
    loadDemoPersonas();
    setNotice('已载入演示角色（重复载入不产生重复条目）。角色数据保存在本机，可编辑或删除。');
  }

  async function handleDelete(persona: PersonaEntry) {
    if (!window.confirm(`删除角色「${persona.name}」？删除后无法恢复。`)) return;
    try {
      deletePersona(persona.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '删除失败，原数据未修改。');
    }
  }

  return (
    /* B-R05-EXT5-I2：space-sections-page 为本批四子页视觉作用域修饰类；
       页面根 space-page 由 SpaceMain 提供（v1 已交付，不动）。 */
    <div className="space-sections-page">
      <SpaceMain
        title="角色目录"
        description="问答的人设来源；聊天输入区「人设」选择与此共享同一份本地目录。"
        actions={
          <>
            <button className="space-button" onClick={handleLoadDemo}>
              <Sparkles size={14} />
              载入演示角色
            </button>
            <button
              className="space-button primary"
              onClick={() => setDialog({ kind: 'edit', persona: null })}
            >
              <UserPlus size={14} />
              新建角色
            </button>
          </>
        }
      >
      {notice && (
        <div className="space-banner info" role="status">
          {notice}
        </div>
      )}
      {error && (
        <div className="space-banner error" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div aria-hidden>
          {[0, 1, 2].map((i) => (
            <div className="space-skeleton" key={i} style={{ height: 92, marginBottom: 10 }} />
          ))}
        </div>
      ) : personas.length === 0 ? (
        <div className="space-empty">
          <strong>还没有角色</strong>
          <span>载入演示角色快速体验，或创建你的第一个讲解人设。</span>
          <div className="space-card-actions">
            <button className="space-button" onClick={handleLoadDemo}>
              <Sparkles size={14} />
              载入演示角色
            </button>
            <button
              className="space-button primary"
              onClick={() => setDialog({ kind: 'edit', persona: null })}
            >
              <UserPlus size={14} />
              新建角色
            </button>
          </div>
        </div>
      ) : (
        <div className="space-card-grid">
          {personas.map((persona) => (
            <article className="space-persona-card" key={persona.id}>
              <div className="space-card-title">
                {persona.name}
                <span className={`space-chip ${persona.source === 'demo' ? 'amber' : ''}`}>
                  {persona.source === 'demo' ? '演示' : '自建'}
                </span>
              </div>
              <p className="space-card-body">{persona.description || '（无简介）'}</p>
              <div className="space-card-actions">
                <button
                  className="space-button"
                  onClick={() => setDialog({ kind: 'view', persona })}
                >
                  <Eye size={14} />
                  查看
                </button>
                <button
                  className="space-button"
                  onClick={() => setDialog({ kind: 'edit', persona })}
                >
                  <Pencil size={14} />
                  编辑
                </button>
                <button
                  className="space-button danger"
                  onClick={() => void handleDelete(persona)}
                >
                  <Trash2 size={14} />
                  删除
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <p className="space-footnote">共 {personas.length} 个角色。数据仅保存在本机浏览器。</p>

      {dialog?.kind === 'view' && (
        <Modal
          title={`角色 · ${dialog.persona.name}`}
          onClose={() => setDialog(null)}
        >
          <div className="space-form">
            <p className="space-card-body">{dialog.persona.description || '（无简介）'}</p>
            {dialog.persona.content ? (
              <div className="space-explanation" style={{ whiteSpace: 'pre-wrap' }}>
                {dialog.persona.content}
              </div>
            ) : (
              <p className="space-footnote">该角色没有正文内容。</p>
            )}
            <div className="space-form-footer">
              <button
                className="space-button"
                onClick={() => setDialog({ kind: 'edit', persona: dialog.persona })}
              >
                <Pencil size={14} />
                编辑
              </button>
            </div>
          </div>
        </Modal>
      )}

      {dialog?.kind === 'edit' && (
        <PersonaForm
          persona={dialog.persona}
          onClose={() => setDialog(null)}
          onSaved={(name) => {
            setDialog(null);
            setNotice(`已保存角色「${name}」。`);
          }}
        />
      )}
      </SpaceMain>
    </div>
  );
}

function PersonaForm({
  persona,
  onClose,
  onSaved,
}: {
  persona: PersonaEntry | null;
  onClose: () => void;
  onSaved: (name: string) => void;
}) {
  const [name, setName] = useState(persona?.name ?? '');
  const [description, setDescription] = useState(persona?.description ?? '');
  const [content, setContent] = useState(persona?.content ?? '');
  const [error, setError] = useState<string | null>(null);

  function submit() {
    try {
      const saved = persona
        ? updatePersona(persona.id, { name, description, content })
        : createPersona({ name, description, content });
      onSaved(saved.name);
    } catch (cause) {
      setError(
        cause instanceof PersonaValidationError
          ? cause.message
          : '保存失败，请检查输入后重试。',
      );
    }
  }

  return (
    <Modal title={persona ? `编辑角色 · ${persona.name}` : '新建角色'} onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label>
          名称
          <input
            value={name}
            required
            maxLength={50}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：耐心的小学老师"
          />
        </label>
        <label>
          简介（进入问答时展示的一句话说明）
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="这个角色如何讲解？"
          />
        </label>
        <label>
          正文（markdown，可选）
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={'# 角色说明\n\n- 讲解风格\n- 常用方法'}
          />
        </label>
        {error && (
          <p className="space-form-error" role="alert">
            {error}
          </p>
        )}
        <div className="space-form-footer">
          <button type="button" className="space-button" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="space-button primary">
            保存
          </button>
        </div>
      </form>
    </Modal>
  );
}
