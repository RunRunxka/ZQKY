'use client';

/**
 * `/knowledge-bases` 教材管理页：基础库 / 我的教材 / 历史登记三个页签 +
 * 导入教材、入库任务两个面板入口。真实数据全部来自 FastAPI（`/api/v1/...`）。
 *
 * 书籍/课程入口（`.kb-library-links`）保留，桌面侧栏没有这两个顶级项时的稳定可达路径。
 */

import { useMemo, useRef, useState } from 'react';
import { useEntrance } from '@/components/motion/useEntrance';
import Link from 'next/link';
import { BookMarked, ChevronRight, GraduationCap, ListChecks, Upload } from 'lucide-react';
// 与既有内容页共享 space 设计语言（只读引入，不修改共享层）
import '@/components/layout/space.css';
import '@/features/textbook/styles/textbook.css';
import type { LibraryKind } from '@/contracts/textbook';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { HistoryRegistrations } from './HistoryRegistrations';
import { ImportPanel } from './ImportPanel';
import { JobsPanel } from './JobsPanel';
import { LIBRARY_KIND_LABEL } from './labels';
import { LibraryBrowser } from './LibraryBrowser';
import { TeachingScopePanel } from './TeachingScopePanel';
import { useAsyncResource } from './hooks';
import { buildTaxonomyIndex } from './taxonomy';

type Tab = LibraryKind | 'history';

export function TextbookWorkspace() {
  const entranceRef = useRef<HTMLDivElement>(null);
  useEntrance(entranceRef, { preset: 'page' });
  const [tab, setTab] = useState<Tab>('base');
  const [importOpen, setImportOpen] = useState(false);
  const [jobsOpen, setJobsOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const taxonomy = useAsyncResource((signal) => fetchTextbookTaxonomy(signal), 'textbook-taxonomy');
  const index = useMemo(
    () => buildTaxonomyIndex(taxonomy.state.phase === 'ready' ? taxonomy.state.data : null),
    [taxonomy.state],
  );

  const tabs: { id: Tab; label: string }[] = [
    { id: 'base', label: LIBRARY_KIND_LABEL.base },
    { id: 'personal', label: LIBRARY_KIND_LABEL.personal },
    { id: 'history', label: '历史登记' },
  ];

  return (
    <div className="space-page textbook-page" ref={entranceRef}>
      <header className="space-header" data-motion-reveal>
        <div className="space-header-row">
          <h1>教材资料库</h1>
          <div className="space-card-actions">
            <button className="space-button" onClick={() => setJobsOpen(true)}>
              <ListChecks size={14} aria-hidden />
              入库任务
            </button>
            <button className="space-button primary" onClick={() => setImportOpen(true)}>
              <Upload size={14} aria-hidden />
              导入教材
            </button>
          </div>
        </div>
        <p className="space-description">
          教材目录、解析入库与可检索范围均以后端为准；导入的原文会保存在服务端并绑定不可变修订。
        </p>
      </header>

      <main className="space-content">
        {/* 任教范围（RAG-QUALITY v1.1 · F2-SCOPE-UI）：只读展示 + 显式修改；页面加载只 GET，不写任何数据 */}
        <TeachingScopePanel taxonomy={index} />

        {/* 书籍/课程入口（T4）：桌面侧栏没有这两个顶级项，这里提供稳定可达路径 */}
        <nav className="kb-library-links" aria-label="教材内容阅读" data-motion-reveal>
          <Link className="kb-library-link" href="/books">
            <span className="kb-library-link-icon" aria-hidden>
              <BookMarked size={18} />
            </span>
            <span className="kb-library-link-body">
              <strong>书籍</strong>
              <span>教材内容阅读</span>
            </span>
            <ChevronRight className="kb-library-link-chevron" size={16} aria-hidden />
          </Link>
          <Link className="kb-library-link" href="/courses">
            <span className="kb-library-link-icon" aria-hidden>
              <GraduationCap size={18} />
            </span>
            <span className="kb-library-link-body">
              <strong>课程</strong>
              <span>大纲与资源关联</span>
            </span>
            <ChevronRight className="kb-library-link-chevron" size={16} aria-hidden />
          </Link>
        </nav>

        <div className="space-tabs" role="tablist" aria-label="教材视图" data-motion-reveal>
          {tabs.map((item) => (
            <button
              key={item.id}
              role="tab"
              id={`textbook-tab-${item.id}`}
              aria-selected={tab === item.id}
              aria-controls={`textbook-panel-${item.id}`}
              className={tab === item.id ? 'current' : ''}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {taxonomy.state.phase === 'failed' && (
          <div className="space-banner error" role="alert">
            教材字典读取失败（{taxonomy.state.error.code}）：{taxonomy.state.error.message}
            筛选与分类选项暂不可用；列表数据不受影响。
            <div className="textbook-panel-actions">
              <button className="space-button" onClick={taxonomy.reload}>
                重试读取字典
              </button>
            </div>
          </div>
        )}

        {notice && (
          <div className="space-banner info" role="status">
            {notice}
            <div className="textbook-panel-actions">
              <button className="space-button" onClick={() => setJobsOpen(true)}>
                查看入库任务
              </button>
              <button className="space-button" onClick={() => setNotice(null)}>
                关闭
              </button>
            </div>
          </div>
        )}

        {tabs.map((item) => (
          <div
            key={item.id}
            id={`textbook-panel-${item.id}`}
            role="tabpanel"
            aria-labelledby={`textbook-tab-${item.id}`}
            hidden={tab !== item.id}
          >
            {item.id === 'history' ? (
              <HistoryRegistrations />
            ) : (
              <LibraryBrowser kind={item.id} taxonomy={index} refreshToken={refreshToken} />
            )}
          </div>
        ))}

        <p className="space-footnote">
          导入需要后端解析、Embedding
          配置与向量库均可用；任一环节失败都会显示具体原因，不会伪造成功。
        </p>
      </main>

      {importOpen && (
        <ImportPanel
          taxonomy={index}
          updateTarget={null}
          onClose={() => setImportOpen(false)}
          onOpenJobs={() => setJobsOpen(true)}
          onCommitted={(job) => {
            setRefreshToken((value) => value + 1);
            setNotice(`已提交入库任务（任务 ${job.jobId}），进度以服务端任务状态为准。`);
          }}
        />
      )}

      {jobsOpen && <JobsPanel onClose={() => setJobsOpen(false)} />}
    </div>
  );
}
