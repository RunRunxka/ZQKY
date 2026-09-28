'use client';

/**
 * `/question-bank` 题库页：导入批次（含导入入口）与已入库题目两个页签。
 * 顶部为同级直接标题（与 /chat、/knowledge-bases 一致），不带面包屑。
 * 真实数据全部来自 FastAPI（`/api/v1/...`）。
 */

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Upload } from 'lucide-react';
// 与既有内容页共享 space 设计语言（只读引入，不修改共享层）
import '@/components/layout/space.css';
import '@/features/question-bank/styles/question-bank.css';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { ImportBatchList } from './ImportBatchList';
import { ImportQuestionPanel } from './ImportQuestionPanel';
import { QuestionLibrary } from './QuestionLibrary';
import { useAsyncResource } from './hooks';
import { buildTaxonomyIndex } from './taxonomy';

type Tab = 'imports' | 'library';

const TABS: { id: Tab; label: string }[] = [
  { id: 'imports', label: '导入批次' },
  { id: 'library', label: '已入库题目' },
];

export function QuestionBankWorkspace() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('imports');
  const [importOpen, setImportOpen] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);

  const taxonomy = useAsyncResource(
    (signal) => fetchTextbookTaxonomy(signal),
    'question-bank-taxonomy',
  );
  const index = useMemo(
    () => buildTaxonomyIndex(taxonomy.state.phase === 'ready' ? taxonomy.state.data : null),
    [taxonomy.state],
  );

  // 校对页「查看已入库题目」跳回时用 hash 定位页签（hash 不参与服务端渲染）。
  useEffect(() => {
    if (window.location.hash === '#library') setTab('library');
  }, []);

  return (
    <div className="space-page question-bank-page">
      <header className="space-header">
        <div className="space-header-row">
          <h1>题库</h1>
          <div className="space-card-actions">
            <button className="space-button primary" onClick={() => setImportOpen(true)}>
              <Upload size={14} aria-hidden />
              导入试题
            </button>
          </div>
        </div>
        <p className="space-description">
          试题来自导入文件的本地解析与规则拆题；AI 整理结果只是待校对建议，必须人工校对后才能入库。
        </p>
      </header>

      <main className="space-content">
        <div className="space-tabs" role="tablist" aria-label="题库视图">
          {TABS.map((item) => (
            <button
              key={item.id}
              role="tab"
              id={`qb-tab-${item.id}`}
              aria-selected={tab === item.id}
              aria-controls={`qb-panel-${item.id}`}
              className={tab === item.id ? 'current' : ''}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {taxonomy.state.phase === 'failed' && (
          <div className="space-banner error" role="alert">
            分类字典读取失败（{taxonomy.state.error.code}）：{taxonomy.state.error.message}
            学科/年级/版本筛选与分类选择暂不可用，可直接填写分类 id；题目与批次数据不受影响。
            <div className="qb-actions">
              <button className="space-button" onClick={taxonomy.reload}>
                重试读取字典
              </button>
            </div>
          </div>
        )}

        <div
          id={`qb-panel-${tab}`}
          role="tabpanel"
          aria-labelledby={`qb-tab-${tab}`}
          className="qb-panel-body"
        >
          {tab === 'imports' ? (
            <ImportBatchList refreshToken={refreshToken} />
          ) : (
            <QuestionLibrary taxonomy={index} />
          )}
        </div>

        <p className="space-footnote">
          导入解析、AI 整理与入库都以后端为准：任何环节失败都会显示具体原因与错误码，不会伪造成功，
          也不会把请求失败当成空列表。
        </p>
      </main>

      {importOpen && (
        <ImportQuestionPanel
          taxonomy={index}
          onClose={() => setImportOpen(false)}
          onImported={(importId) => {
            setImportOpen(false);
            setRefreshToken((value) => value + 1);
            router.push(`/question-bank/imports/${importId}`);
          }}
        />
      )}
    </div>
  );
}
