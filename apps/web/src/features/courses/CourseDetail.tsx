'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, BookMarked, FolderOpen, Library, Plus, Trash2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import {
  COURSE_COLOR_DOT,
  COURSE_COLORS,
  COURSE_KIND_LABEL,
  CourseValidationError,
  attachCourseResource,
  courseResourceStates,
  deleteCourse,
  detachCourseResource,
  listResourceCandidates,
  readResourceDirectories,
  snapshotError,
  subscribeResourceDirectories,
  parseSyllabusText,
  readCourses,
  setCourseArchived,
  setCourseSyllabus,
  subscribeCourses,
  syllabusSummary,
  toggleUnitCovered,
  updateCourse,
  type CourseColor,
  type CourseResourceKind,
  type ResourceDirectorySnapshot,
  type StudyCourse,
} from '@/services/courses-store';
import '@/features/space/styles/space.css';

export function CourseDetail() {
  const params = useParams<{ courseId: string }>();
  const courseId = params?.courseId;
  const router = useRouter();
  const [courses, setCourses] = useState<StudyCourse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editingSyllabus, setEditingSyllabus] = useState(false);
  const [syllabusText, setSyllabusText] = useState('');
  const [addingResource, setAddingResource] = useState(false);
  // R-11：资源目录在 effect 中集中读取为一致快照（渲染期不再读目录），失败可重试
  const [directories, setDirectories] = useState<ResourceDirectorySnapshot | null>(null);

  const refresh = useCallback(() => {
    try {
      setCourses(readCourses());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '课程目录无法读取，原数据未修改。');
    }
  }, []);

  /** 集中读取资源目录快照；再次调用即"重试"（数据修复后无需清空浏览器数据）。 */
  const refreshDirectories = useCallback(() => {
    setDirectories(readResourceDirectories());
  }, []);

  useEffect(() => {
    refresh();
    // 资源目录变化（知识库/笔记本/书籍）时失效快照并重算，不再依赖手动刷新
    return subscribeCourses(refresh);
  }, [refresh]);

  useEffect(() => {
    refreshDirectories();
    return subscribeResourceDirectories(refreshDirectories);
  }, [refreshDirectories]);

  const course = useMemo(
    () => courses?.find((item) => item.id === courseId) ?? null,
    [courses, courseId],
  );

  if (courses !== null && !course) {
    return (
      <div className="space-page">
        <div className="space-empty" style={{ marginTop: 80 }}>
          <strong>课程不存在或已被删除</strong>
          <span>它可能已被删除，或链接有误。</span>
          <Link className="space-button" href="/courses">
            <ArrowLeft size={14} />
            返回课程列表
          </Link>
        </div>
      </div>
    );
  }

  if (!course) {
    return (
      <div className="space-page">
        <div className="space-banner" style={{ marginTop: 80 }}>
          正在读取课程…
        </div>
      </div>
    );
  }

  const summary = syllabusSummary(course);
  // 快照尚未就绪时先按空快照渲染（不触发目录读取）；就绪后由 effect 重算
  const resources = courseResourceStates(
    course,
    directories ?? { knowledge: [], knowledgeError: null, notebooks: [], notebooksError: null, books: [], booksError: null },
  );
  const directoryError = directories ? snapshotError(directories) : null;

  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/courses">
            <ArrowLeft size={16} />
            返回课程列表
          </Link>
          <div className="space-card-actions">
            <button className="space-button" onClick={() => setEditing(true)}>
              编辑
            </button>
            <button
              className="space-button"
              onClick={() => {
                const archived = course.status === 'active';
                setCourseArchived(course.id, archived);
                setNotice(archived ? '已归档课程（列表折叠区可见）。' : '已恢复课程。');
              }}
            >
              {course.status === 'active' ? '归档' : '恢复'}
            </button>
            <button
              className="space-button danger"
              onClick={() => {
                if (window.confirm(`删除课程「${course.name}」？仅移除本地目录登记。`)) {
                  if (deleteCourse(course.id)) router.push('/courses');
                  else setError('删除失败：课程不存在或已被删除。');
                }
              }}
            >
              <Trash2 size={14} />
              删除
            </button>
          </div>
        </div>
        <h1>
          <span
            aria-hidden
            style={{
              display: 'inline-block',
              width: 12,
              height: 12,
              borderRadius: 999,
              background: COURSE_COLOR_DOT[course.color],
              marginRight: 10,
            }}
          />
          {course.name}
          {course.status === 'archived' && (
            <span className="space-chip" style={{ marginLeft: 10 }}>
              已归档
            </span>
          )}
        </h1>
        <p className="space-description">{course.description || '（无简介）'}</p>
      </header>
      <main className="space-content">
        <div className="space-banner info" role="note">
          课程学习会话未接入：参考以 session.preferences.course_id 过滤课程会话，目标项目聊天会话尚未携带课程标记；
          大纲与资料为本地目录，聚合进度（掌握/题库/阅读）未接入。
        </div>
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

        {/* 大纲 */}
        <section className="space-group">
          <div className="space-header-row">
            <h2 className="space-group-label">
              大纲（{summary.covered}/{summary.total} 已完成
              {summary.next ? `，下一单元：${summary.next.title}` : '，全部完成'}）
            </h2>
            <div className="space-card-actions">
              <button
                className="space-button"
                onClick={() => {
                  setSyllabusText(
                    course.syllabus
                      .map((unit) => [unit.title, unit.topics.join(', ')].filter(Boolean).join(' | '))
                      .join('\n'),
                  );
                  setEditingSyllabus((current) => !current);
                }}
              >
                {editingSyllabus ? '收起编辑' : '编辑大纲'}
              </button>
            </div>
          </div>
          {editingSyllabus && (
            <div className="space-category-manager" style={{ marginBottom: 10 }}>
              <p className="space-footnote" style={{ marginTop: 0 }}>
                每行一个单元，格式「标题 | 主题1, 主题2」；保存会重建大纲（covered 重置为未完成）。
              </p>
              <textarea
                className="space-search"
                style={{ width: '100%', minHeight: 96 }}
                aria-label="大纲文本"
                value={syllabusText}
                onChange={(event) => setSyllabusText(event.target.value)}
              />
              <div className="space-card-actions">
                <button
                  className="space-button primary"
                  onClick={() => {
                    setCourseSyllabus(course.id, parseSyllabusText(syllabusText));
                    setEditingSyllabus(false);
                    setNotice('已保存大纲（covered 已重置，由学员重新勾选）。');
                  }}
                >
                  保存大纲
                </button>
                <button className="space-button" onClick={() => setEditingSyllabus(false)}>
                  取消
                </button>
              </div>
            </div>
          )}
          {course.syllabus.length === 0 ? (
            <div className="space-empty">
              <strong>还没有大纲</strong>
              <span>点「编辑大纲」按「标题 | 主题1, 主题2」逐行添加学习单元。</span>
            </div>
          ) : (
            <ul className="space-session-list">
              {course.syllabus.map((unit) => (
                <li className="space-session-card" key={unit.id}>
                  <div className="space-session-top">
                    <input
                      type="checkbox"
                      checked={unit.covered}
                      onChange={() => toggleUnitCovered(course.id, unit.id)}
                      aria-label={`标记「${unit.title}」为已完成`}
                    />
                    <span className="space-session-title" style={unit.covered ? { opacity: 0.7 } : undefined}>
                      {unit.title}
                    </span>
                    {summary.next?.id === unit.id && <span className="space-chip blue">下一单元</span>}
                    {unit.covered && <span className="space-chip green">已完成</span>}
                  </div>
                  {unit.topics.length > 0 && (
                    <div className="space-meta-row">
                      {unit.topics.map((topic) => (
                        <span className="space-chip" key={topic}>
                          {topic}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 资源 */}
        <section className="space-group">
          <div className="space-header-row">
            <h2 className="space-group-label">课程资料（{resources.length}）</h2>
            <div className="space-card-actions">
              <button className="space-button" onClick={() => setAddingResource(true)}>
                <Plus size={14} />
                附加资料
              </button>
            </div>
          </div>
          {directoryError && (
            <div className="space-banner error" role="alert">
              <div className="space-banner-row">
                <span>资源目录读取失败：{directoryError}</span>
                <button className="space-button" onClick={refreshDirectories}>
                  重试
                </button>
              </div>
            </div>
          )}
          {resources.length === 0 ? (
            <div className="space-empty">
              <strong>还没有附加资料</strong>
              <span>从知识库、笔记本、书籍目录附加，或先到对应页面创建。</span>
            </div>
          ) : (
            <ul className="space-session-list">
              {resources.map(({ resource, availability, href }) => (
                <li className="space-session-card" key={resource.id}>
                  <div className="space-session-top">
                    <span className="space-chip">{COURSE_KIND_LABEL[resource.kind]}</span>
                    {availability === 'available' && href ? (
                      <Link className="space-session-title" href={href}>
                        {resource.label}
                      </Link>
                    ) : availability === 'unknown' ? (
                      // R-11：目录读取失败不能断言目标已删除，明确说明无法确认
                      <span className="space-session-title" style={{ opacity: 0.6 }}>
                        {resource.label}（目录读取失败，暂无法确认）
                      </span>
                    ) : (
                      <span className="space-session-title" style={{ opacity: 0.6 }}>
                        {resource.label}（不可用：目标已删除或未载入）
                      </span>
                    )}
                    <span className="space-session-actions">
                      <button
                        className="icon-button"
                        aria-label={`移除资料 ${resource.label}`}
                        onClick={() => {
                          detachCourseResource(course.id, resource.id);
                          setNotice(`已移除资料「${resource.label}」。`);
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <p className="space-footnote">
            新建关联设施：
            <Link href="/knowledge-bases"> 教材资料库</Link> ·<Link href="/notebooks"> 笔记本</Link> ·
            <Link href="/books"> 书籍</Link>（创建后回到本页附加）。
          </p>
        </section>

        {/* 约定 */}
        <section className="space-group">
          <h2 className="space-group-label">学习约定</h2>
          {course.instructions ? (
            <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{course.instructions}</p>
          ) : (
            <p className="space-footnote" style={{ margin: 0 }}>
              暂无约定；通过「编辑」填写（参考为每次对话注入的课程 instructions）。
            </p>
          )}
        </section>
      </main>

      {editing && (
        <EditCourseForm
          course={course}
          onClose={() => setEditing(false)}
          onSaved={(name) => {
            setEditing(false);
            setNotice(`已保存「${name}」。`);
          }}
        />
      )}

      {addingResource && (
        <AddResourceForm
          course={course}
          directories={directories}
          onRetryDirectories={refreshDirectories}
          onClose={() => setAddingResource(false)}
          onAdded={(label) => {
            setAddingResource(false);
            setNotice(`已附加资料「${label}」。`);
          }}
        />
      )}
    </div>
  );
}

function EditCourseForm({
  course,
  onClose,
  onSaved,
}: {
  course: StudyCourse;
  onClose: () => void;
  onSaved: (name: string) => void;
}) {
  const [name, setName] = useState(course.name);
  const [description, setDescription] = useState(course.description);
  const [color, setColor] = useState<CourseColor>(course.color);
  const [instructions, setInstructions] = useState(course.instructions);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title={`编辑课程 · ${course.name}`} onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            const updated = updateCourse(course.id, { name, description, color, instructions });
            onSaved(updated.name);
          } catch (cause) {
            setError(
              cause instanceof CourseValidationError ? cause.message : '保存失败，请检查输入后重试。',
            );
          }
        }}
      >
        <label>
          名称
          <input value={name} required maxLength={60} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          简介
          <input value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label>
          学习约定（每次对话注入的课程 instructions）
          <textarea
            value={instructions}
            style={{ minHeight: 72 }}
            onChange={(event) => setInstructions(event.target.value)}
          />
        </label>
        <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="space-footnote" style={{ padding: 0 }}>
            颜色标记
          </legend>
          <div className="space-card-actions">
            {COURSE_COLORS.map((value) => (
              <button
                type="button"
                key={value}
                aria-label={`颜色 ${value}`}
                aria-pressed={color === value}
                onClick={() => setColor(value)}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 999,
                  background: COURSE_COLOR_DOT[value],
                  outline: color === value ? '2px solid var(--ink)' : 'none',
                  outlineOffset: 2,
                }}
              />
            ))}
          </div>
        </fieldset>
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

const KIND_ICON: Record<CourseResourceKind, typeof Library> = {
  knowledge_base: Library,
  notebook: FolderOpen,
  book: BookMarked,
};

function AddResourceForm({
  course,
  directories,
  onRetryDirectories,
  onClose,
  onAdded,
}: {
  course: StudyCourse;
  /** R-11：来自父层的目录快照；弹窗不再自行读取目录（避免渲染期读取与无法重试） */
  directories: ResourceDirectorySnapshot | null;
  onRetryDirectories: () => void;
  onClose: () => void;
  onAdded: (label: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const directoryError = directories ? snapshotError(directories) : null;
  const candidates = useMemo(() => listResourceCandidates(directories ?? undefined), [directories]);
  const attachedKeys = new Set(course.resources.map((item) => `${item.kind}:${item.refId}`));
  const groups: CourseResourceKind[] = ['knowledge_base', 'notebook', 'book'];
  return (
    <Modal title="附加课程资料" onClose={onClose}>
      {/* R-11：某个目录读取失败只提示该目录，不阻断其他目录的候选 */}
      {directoryError && (
        <div className="space-banner error" role="alert">
          <div className="space-banner-row">
            <span>部分资源目录读取失败：{directoryError}</span>
            <button className="space-button" onClick={onRetryDirectories}>
              重试
            </button>
          </div>
        </div>
      )}
      {candidates.length === 0 && !directoryError ? (
        <div className="space-empty">
          <strong>本地目录为空</strong>
          <span>先到教材资料库 / 笔记本 / 书籍创建或载入演示数据，再回来附加。</span>
          <div className="space-form-footer" style={{ width: '100%' }}>
            <button className="space-button" onClick={onClose}>
              关闭
            </button>
          </div>
        </div>
      ) : (
        <div className="space-category-manager">
          {error && (
            <p className="space-form-error" role="alert">
              {error}
            </p>
          )}
          {groups.map((kind) => {
            const items = candidates.filter((item) => item.kind === kind);
            if (items.length === 0) return null;
            const Icon = KIND_ICON[kind];
            return (
              <section className="space-group" key={kind}>
                <h3 className="space-group-label">{COURSE_KIND_LABEL[kind]}</h3>
                <ul className="space-session-list">
                  {items.map((item) => {
                    const attached = attachedKeys.has(`${item.kind}:${item.refId}`);
                    return (
                      <li className="space-session-card" key={`${item.kind}:${item.refId}`}>
                        <div className="space-session-top">
                          <Icon size={14} aria-hidden />
                          <span className="space-session-title">{item.label}</span>
                          <span className="space-session-actions">
                            <button
                              className="space-button"
                              disabled={attached}
                              onClick={() => {
                                try {
                                  attachCourseResource(course.id, item.kind, item.refId, item.label);
                                  onAdded(item.label);
                                } catch (cause) {
                                  setError(
                                    cause instanceof CourseValidationError
                                      ? cause.message
                                      : '附加失败，请重试。',
                                  );
                                }
                              }}
                            >
                              {attached ? '已附加' : '附加'}
                            </button>
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </Modal>
  );
}
