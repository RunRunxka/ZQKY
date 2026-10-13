'use client';

/**
 * 新建逻辑库（R10-FE，2026-10-13）：教材资料库此前**没有任何建库入口**，
 * 而导入流程第 4 步「加入逻辑库」要求至少选一个库 → 空库时导入无法完成。
 *
 * 逻辑库 = 教材册的归属/检索范围容器：`kind`（基础库 / 我的教材）+ 学科 + 版本（+ 可选年级）。
 * 表单字段与后端 `POST /textbook-libraries`（`LibraryCreateRequest`）逐项对应：
 * `kind` / `displayName` / `subjectId` / `editionId` / `gradeId?`。
 *
 * 纪律：字典未就绪（分类读取失败）时**不让提交**并说明原因；提交失败原样展示服务端
 * code 与 message（不伪造成功）；成功后由父组件刷新库列表并给提示。
 */

import { useState } from 'react';
import { LoaderCircle, Plus } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import type { LibraryKind, LibrarySummary } from '@/contracts/textbook';
import { createLibrary } from '@/services/textbook-api';
import { asApiError } from './hooks';
import { LIBRARY_KIND_LABEL } from './labels';
import type { TaxonomyIndex } from './taxonomy';

export function LibraryCreateDialog({
  taxonomy,
  defaultKind = 'personal',
  onClose,
  onCreated,
}: {
  taxonomy: TaxonomyIndex;
  /** 打开时的默认类型：我的教材（个人库）为主；基础库一般由服务端成套建立。 */
  defaultKind?: LibraryKind;
  onClose: () => void;
  onCreated: (created: LibrarySummary) => void;
}) {
  const [kind, setKind] = useState<LibraryKind>(defaultKind);
  const [displayName, setDisplayName] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [editionId, setEditionId] = useState('');
  const [gradeId, setGradeId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = taxonomy.ready;
  const canSubmit =
    !busy && displayName.trim().length > 0 && subjectId !== '' && editionId !== '';

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createLibrary({
        kind,
        displayName: displayName.trim(),
        subjectId,
        editionId,
        gradeId: gradeId === '' ? null : gradeId,
      });
      onCreated(created);
    } catch (cause) {
      const issue = asApiError(cause);
      setError(`新建逻辑库失败（${issue.code}）：${issue.message} 输入已保留，可修改后重试。`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="新建逻辑库" onClose={onClose}>
      <form
        className="textbook-form"
        aria-label="新建逻辑库"
        data-testid="textbook-library-create"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <p className="textbook-hint">
          逻辑库是教材册的归属与检索范围（导入第 4 步要选它）。个人库放自己上传/整理的教材；
          基础库按学年成套由服务端建立，这里一般建「我的教材」。
        </p>
        <label className="textbook-field">
          <span>类型</span>
          <select
            className="space-select"
            aria-label="库类型"
            value={kind}
            disabled={busy}
            onChange={(event) => setKind(event.target.value as LibraryKind)}
          >
            <option value="personal">{LIBRARY_KIND_LABEL.personal}</option>
            <option value="base">{LIBRARY_KIND_LABEL.base}</option>
          </select>
        </label>
        <label className="textbook-field">
          <span>显示名</span>
          <input
            className="textbook-input"
            aria-label="库显示名"
            placeholder="如：我的教材"
            maxLength={120}
            value={displayName}
            disabled={busy}
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </label>
        <label className="textbook-field">
          <span>学科</span>
          <select
            className="space-select"
            aria-label="库学科"
            value={subjectId}
            disabled={busy || !ready}
            onChange={(event) => setSubjectId(event.target.value)}
          >
            <option value="">请选择学科</option>
            {taxonomy.subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.label}
              </option>
            ))}
          </select>
        </label>
        <label className="textbook-field">
          <span>版本</span>
          <select
            className="space-select"
            aria-label="库版本"
            value={editionId}
            disabled={busy || !ready}
            onChange={(event) => setEditionId(event.target.value)}
          >
            <option value="">请选择版本</option>
            {taxonomy.editions.map((edition) => (
              <option key={edition.id} value={edition.id}>
                {edition.label}
              </option>
            ))}
          </select>
        </label>
        <label className="textbook-field">
          <span>年级（可留空）</span>
          <select
            className="space-select"
            aria-label="库年级"
            value={gradeId}
            disabled={busy || !ready}
            onChange={(event) => setGradeId(event.target.value)}
          >
            <option value="">不限定年级</option>
            {taxonomy.grades.map((grade) => (
              <option key={grade.id} value={grade.id}>
                {grade.label}
              </option>
            ))}
          </select>
        </label>
        {!ready && (
          <p className="space-banner error" role="alert" data-testid="textbook-library-create-dict-error">
            分类字典（学科/版本/年级）不可用：无法建立逻辑库。请先在上方重试读取字典。
          </p>
        )}
        {error && (
          <p className="space-banner error" role="alert" data-testid="textbook-library-create-error">
            {error}
          </p>
        )}
        <div className="textbook-form-footer">
          <button className="space-button" type="button" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button
            className="space-button primary"
            type="submit"
            data-testid="textbook-library-create-submit"
            disabled={!canSubmit}
          >
            {busy ? <LoaderCircle size={14} className="lw-spin" aria-hidden /> : <Plus size={14} aria-hidden />}
            {busy ? '建立中…' : '建立逻辑库'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
