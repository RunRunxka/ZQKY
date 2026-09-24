'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Loader2, MessagesSquare, RefreshCcw, SquarePen } from 'lucide-react';
import type { ConversationMeta } from '@/contracts/chat';
import { createIdbChatRepository } from '@/services/chat-repository';
import { buildNewConversation, listCourseSessions } from '@/services/course-session';
import type { StudyCourse } from '@/services/courses-store';

/**
 * 课程学习会话区（H1-COURSE-SESSIONS v1）。
 *
 * - 只读既有会话库（IndexedDB `zhiqikeyuan-chat`）：**不建第二套会话库**，不做模拟问答；
 * - 归属只认 `ConversationMeta.courseId === course.id`（稳定 id），不按标题/最近访问/URL 猜测；
 * - 「新建学习会话」**保存成功后才跳转**：失败保留本页状态与原因、可重试，busy 期间（含同一 tick 连点）
 *   只允许一次创建，因此不会产生重复会话；
 * - 归档课程为只读：新建禁用并说明，既有会话仍可打开（保留历史）。
 */
export function CourseSessions({ course }: { course: StudyCourse }) {
  const router = useRouter();
  const repository = useMemo(() => createIdbChatRepository('zhiqikeyuan-chat'), []);
  const [metas, setMetas] = useState<ConversationMeta[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  /** 同步防重入（同一 tick 连点两次时 state 尚未提交，必须用 ref 兜住） */
  const creatingRef = useRef(false);

  const refresh = useCallback(() => {
    void (async () => {
      try {
        setMetas(await repository.list());
        setLoadError(null);
      } catch (cause) {
        setLoadError(
          cause instanceof Error ? cause.message : '会话目录无法读取，原数据未修改。',
        );
      }
    })();
  }, [repository]);

  useEffect(() => {
    refresh();
  }, [refresh, course.id]);

  const sessions = useMemo(
    () => (metas ? listCourseSessions(metas, course.id) : []),
    [metas, course.id],
  );

  const archived = course.status === 'archived';

  const createSession = () => {
    if (creatingRef.current || archived) return;
    creatingRef.current = true;
    setCreating(true);
    setSaveError(null);
    void (async () => {
      let conversation: ReturnType<typeof buildNewConversation>;
      try {
        conversation = buildNewConversation({
          id: crypto.randomUUID(),
          courseId: course.id,
        });
        // 保存成功后才跳转（失败不跳转、不留半成品，用户可重试）
        await repository.save(conversation);
      } catch (cause) {
        // 保存失败：释放守卫、保留本页状态，用户可重试
        creatingRef.current = false;
        setCreating(false);
        setSaveError(
          cause instanceof Error
            ? `新建学习会话失败：${cause.message}`
            : '新建学习会话失败：本地保存未成功，请重试。',
        );
        return;
      }
      // 保存成功：**守卫保持到本页卸载**。`router.push` 之后到路由卸载之间仍有窗口，
      // 这段时间内再次点击不能进入第二条创建（A1 r1 复现：间隔 10–25ms 会创建重复会话）。
      router.push(`/chat/${conversation.id}`);
    })();
  };

  return (
    <section className="space-group courses-sessions" aria-label="学习会话">
      <div className="space-header-row">
        <h2 className="space-group-label">
          学习会话{sessions.length > 0 ? `（${sessions.length}）` : ''}
        </h2>
        <div className="space-card-actions">
          <button
            type="button"
            className="space-button primary"
            disabled={creating || archived}
            title={archived ? '已归档课程：会话只读，仍可打开既有会话。' : undefined}
            onClick={createSession}
          >
            {creating ? (
              <Loader2 size={13} className="space-spin" aria-hidden />
            ) : (
              <SquarePen size={13} aria-hidden />
            )}
            {creating ? '正在创建…' : '新建学习会话'}
          </button>
        </div>
      </div>

      <p className="space-footnote" style={{ marginTop: 0 }}>
        会话归属按课程 id 保存（旧会话未归属时不会被改写）；发送时把课程名与约定冻结为本轮快照，经既有真实问答链路
        （`/api/v1/chat/stream` 的 system 上下文）参与回答；课程资料只是**登记引用**，未解析、未检索、未随请求发送
        （RAG 未接入）。大纲进度为学员手判，不推断掌握度。
      </p>

      {archived && (
        <div className="space-banner info" role="note">
          已归档课程：学习会话为只读（新建入口已禁用），既有会话仍可打开，历史消息不会被改写。
        </div>
      )}

      {saveError && (
        <div className="space-banner error" role="alert">
          <div className="space-banner-row">
            <span>{saveError}</span>
            <button className="space-button" onClick={createSession} disabled={creating}>
              重试新建
            </button>
          </div>
        </div>
      )}

      {loadError ? (
        <div className="space-banner error" role="alert">
          <div className="space-banner-row">
            <span>学习会话读取失败：{loadError}</span>
            <button className="space-button" onClick={refresh}>
              重试
            </button>
          </div>
        </div>
      ) : metas === null ? (
        <div className="books-loading" role="status">
          <Loader2 size={14} className="space-spin" aria-hidden />
          正在读取学习会话…
        </div>
      ) : sessions.length === 0 ? (
        <div className="space-empty">
          <strong>本课程还没有学习会话</strong>
          <span>
            新建会话后进入学习问答；课程名与约定会随本轮冻结并真实参与回答，返回本页可继续原会话。
          </span>
        </div>
      ) : (
        <ul className="space-session-list">
          {sessions.map((session) => (
            <li className="space-session-card" key={session.id}>
              <Link
                className="space-card-link"
                href={`/chat/${session.id}`}
                aria-label={`打开会话 ${session.title}`}
              >
                <div className="space-session-top">
                  <span className="space-session-title">
                    <MessagesSquare size={13} aria-hidden style={{ marginRight: 6, verticalAlign: -2 }} />
                    {session.title}
                  </span>
                  <span className="space-chip">{session.messageCount} 条消息</span>
                </div>
                <span className="space-footnote">
                  更新于 {new Date(session.updatedAt).toLocaleString('zh-CN')}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {sessions.length > 0 && (
        <div className="space-card-actions">
          <Link className="space-button" href={`/chat/${sessions[0]!.id}`}>
            <RefreshCcw size={13} aria-hidden />
            继续最近会话
          </Link>
        </div>
      )}
    </section>
  );
}
